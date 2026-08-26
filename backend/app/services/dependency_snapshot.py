from __future__ import annotations

from dataclasses import dataclass

from app.dependency import (
    DependencyViewBuilder,
    DependencyViewReport,
    DependencyViewWarning,
    DeviceTreeDependencyExtractor,
)
from app.interrupts import (
    InterruptCorrelationService,
    InterruptCorrelationWarning,
)
from app.model.devicetree import ParseResult
from app.runtime import RuntimeCollection, RuntimeInterrupt, RuntimeProvider
from app.runtime.model import RuntimeWarning
from app.services.devicetree_state import DeviceTreeState


@dataclass(frozen=True)
class DependencySourceError(Exception):
    source: str | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class DependencySnapshotService:
    def __init__(
        self,
        *,
        devicetree_state: DeviceTreeState,
        runtime_provider: RuntimeProvider,
        dependency_extractor: DeviceTreeDependencyExtractor,
        interrupt_correlation_service: InterruptCorrelationService,
        dependency_view_builder: DependencyViewBuilder,
    ) -> None:
        self._devicetree_state = devicetree_state
        self._runtime_provider = runtime_provider
        self._dependency_extractor = dependency_extractor
        self._interrupt_correlation_service = interrupt_correlation_service
        self._dependency_view_builder = dependency_view_builder

    def build_report(self) -> DependencyViewReport:
        parse_result = self._devicetree_state.collect()
        if parse_result.tree is None:
            raise DependencySourceError(
                source=parse_result.source,
                warnings=parse_result.warnings,
                errors=parse_result.errors,
            )

        dependencies = self._dependency_extractor.extract(parse_result.tree)
        interrupts = self._runtime_provider.collect_interrupts()
        interrupt_report = self._interrupt_correlation_service.correlate(
            tree=parse_result.tree,
            dependencies=dependencies,
            interrupts=interrupts.data,
            interrupts_complete=_interrupts_source_complete(interrupts),
        )
        dependency_report = self._dependency_view_builder.build(
            dependencies=dependencies,
            interrupt_correlations=interrupt_report.correlations,
        )

        return DependencyViewReport(
            devices=dependency_report.devices,
            warnings=(
                _parse_warnings_to_dependency_warnings(parse_result)
                + _runtime_warnings_to_dependency_warnings(interrupts.warnings)
                + _interrupt_warnings_to_dependency_warnings(
                    interrupt_report.warnings
                )
                + dependency_report.warnings
            ),
        )


def _parse_warnings_to_dependency_warnings(
    result: ParseResult,
) -> tuple[DependencyViewWarning, ...]:
    return tuple(
        DependencyViewWarning(
            code="DT_PARSE_WARNING",
            message=warning,
        )
        for warning in result.warnings
    )


def _runtime_warnings_to_dependency_warnings(
    warnings: tuple[RuntimeWarning, ...],
) -> tuple[DependencyViewWarning, ...]:
    return tuple(
        DependencyViewWarning(
            code=warning.code,
            message=warning.message,
            source_path=warning.source_path,
        )
        for warning in warnings
    )


def _interrupt_warnings_to_dependency_warnings(
    warnings: tuple[InterruptCorrelationWarning, ...],
) -> tuple[DependencyViewWarning, ...]:
    return tuple(
        DependencyViewWarning(
            code=warning.code,
            message=warning.message,
            consumer_dt_path=warning.consumer_dt_path,
            provider_dt_path=warning.provider_dt_path,
            runtime_irq=warning.runtime_irq,
            source_path=warning.source_path,
        )
        for warning in warnings
    )


def _interrupts_source_complete(
    collection: RuntimeCollection[tuple[RuntimeInterrupt, ...]],
) -> bool:
    incomplete_codes = {
        "PROC_INTERRUPTS_READ_FAILED",
        "PROC_INTERRUPTS_PARSE_FAILED",
    }
    return not any(
        warning.code in incomplete_codes
        for warning in collection.warnings
    )
