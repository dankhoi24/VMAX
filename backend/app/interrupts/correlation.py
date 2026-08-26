from __future__ import annotations

from app.dependency.model import DependencyKind, DependencyReference, DependencyResolution
from app.interrupts.identity import InterruptIdentityExtractor
from app.interrupts.model import (
    InterruptCorrelation,
    InterruptCorrelationReport,
    InterruptCorrelationResolution,
    InterruptCorrelationWarning,
    InterruptIdentity,
    InterruptMatchMethod,
)
from app.model.devicetree import DeviceTree
from app.runtime.model import RuntimeInterrupt


class InterruptCorrelationService:
    def __init__(
        self,
        identity_extractor: InterruptIdentityExtractor | None = None,
    ) -> None:
        self._identity_extractor = identity_extractor or InterruptIdentityExtractor()

    def correlate(
        self,
        *,
        tree: DeviceTree,
        dependencies: tuple[DependencyReference, ...],
        interrupts: tuple[RuntimeInterrupt, ...],
        interrupts_complete: bool = True,
    ) -> InterruptCorrelationReport:
        warnings: list[InterruptCorrelationWarning] = []
        runtime_by_identity = _index_runtime_interrupts(
            interrupts,
            self._identity_extractor,
        )
        correlations: list[InterruptCorrelation] = []

        for dependency in dependencies:
            if dependency.kind != DependencyKind.INTERRUPT:
                continue

            correlation = self._correlate_dependency(
                tree=tree,
                dependency=dependency,
                runtime_by_identity=runtime_by_identity,
                interrupts_complete=interrupts_complete,
            )
            correlations.append(correlation)
            warnings.extend(correlation.warnings)

        return InterruptCorrelationReport(
            correlations=tuple(correlations),
            warnings=tuple(warnings),
        )

    def _correlate_dependency(
        self,
        *,
        tree: DeviceTree,
        dependency: DependencyReference,
        runtime_by_identity: dict[tuple[str, int], tuple[RuntimeInterrupt, ...]],
        interrupts_complete: bool,
    ) -> InterruptCorrelation:
        dt_identities, identity_warnings = self._identity_extractor.dt_identities(
            dependency,
            tree,
        )
        warnings = list(identity_warnings)

        if dependency.resolution == DependencyResolution.AMBIGUOUS:
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=dt_identities,
                resolution=InterruptCorrelationResolution.AMBIGUOUS,
                warnings=tuple(warnings),
            )

        if dependency.resolution == DependencyResolution.UNAVAILABLE:
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=dt_identities,
                resolution=InterruptCorrelationResolution.UNAVAILABLE,
                warnings=tuple(warnings),
            )

        if dependency.resolution == DependencyResolution.UNRESOLVED:
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=dt_identities,
                resolution=InterruptCorrelationResolution.UNRESOLVED,
                warnings=tuple(warnings),
            )

        if not dt_identities:
            warnings.append(
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_IDENTITY_UNAVAILABLE",
                    consumer_dt_path=dependency.consumer_dt_path,
                    provider_dt_path=dependency.provider_dt_path,
                    source_path=_reference_source_path(dependency),
                    message=(
                        "DT interrupt specifier could not be interpreted as a "
                        "supported runtime IRQ identity"
                    ),
                )
            )
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=(),
                resolution=InterruptCorrelationResolution.UNAVAILABLE,
                warnings=tuple(warnings),
            )

        runtime_candidates = _runtime_candidates_for_dt_identities(
            dt_identities,
            runtime_by_identity,
        )
        if len(runtime_candidates) == 1:
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=dt_identities,
                runtime_interrupt=runtime_candidates[0],
                runtime_candidates=runtime_candidates,
                resolution=InterruptCorrelationResolution.RESOLVED,
                match_method=InterruptMatchMethod.CONTROLLER_HARDWARE_IRQ,
                warnings=tuple(warnings),
            )

        if len(runtime_candidates) > 1:
            warnings.append(
                InterruptCorrelationWarning(
                    code="RUNTIME_INTERRUPT_MATCH_AMBIGUOUS",
                    consumer_dt_path=dependency.consumer_dt_path,
                    provider_dt_path=dependency.provider_dt_path,
                    source_path=_reference_source_path(dependency),
                    message=(
                        "DT interrupt identity matches multiple runtime IRQs "
                        "by controller and hardware IRQ"
                    ),
                )
            )
            return InterruptCorrelation(
                dependency=dependency,
                dt_identities=dt_identities,
                runtime_candidates=runtime_candidates,
                resolution=InterruptCorrelationResolution.AMBIGUOUS,
                match_method=InterruptMatchMethod.CONTROLLER_HARDWARE_IRQ,
                warnings=tuple(warnings),
            )

        return InterruptCorrelation(
            dependency=dependency,
            dt_identities=dt_identities,
            resolution=(
                InterruptCorrelationResolution.UNRESOLVED
                if interrupts_complete
                else InterruptCorrelationResolution.UNAVAILABLE
            ),
            warnings=tuple(warnings),
        )


def _index_runtime_interrupts(
    interrupts: tuple[RuntimeInterrupt, ...],
    identity_extractor: InterruptIdentityExtractor,
) -> dict[tuple[str, int], tuple[RuntimeInterrupt, ...]]:
    indexed: dict[tuple[str, int], list[RuntimeInterrupt]] = {}
    for interrupt in interrupts:
        identity = identity_extractor.runtime_identity(interrupt)
        if identity is None:
            continue
        indexed.setdefault(
            (identity.controller_key, identity.hardware_irq),
            [],
        ).append(interrupt)

    return {key: tuple(value) for key, value in indexed.items()}


def _runtime_candidates_for_dt_identities(
    dt_identities: tuple[InterruptIdentity, ...],
    runtime_by_identity: dict[tuple[str, int], tuple[RuntimeInterrupt, ...]],
) -> tuple[RuntimeInterrupt, ...]:
    candidates: list[RuntimeInterrupt] = []
    seen_irqs: set[int] = set()
    for identity in dt_identities:
        key = (identity.controller_key, identity.hardware_irq)
        for interrupt in runtime_by_identity.get(key, ()):
            if interrupt.irq in seen_irqs:
                continue
            seen_irqs.add(interrupt.irq)
            candidates.append(interrupt)
    return tuple(candidates)


def _reference_source_path(reference: DependencyReference) -> str | None:
    for evidence in reference.evidence:
        if evidence.source_path is not None:
            return evidence.source_path
    return None
