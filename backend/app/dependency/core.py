from __future__ import annotations

from dataclasses import dataclass, field

from app.dependency.model import (
    DependencyKind,
    DependencyReference,
    DependencyResolution,
)
from app.interrupts.model import (
    InterruptCorrelation,
    InterruptCorrelationResolution,
    InterruptCorrelationWarning,
)
from app.runtime.model import RuntimeInterrupt


_KIND_ORDER = {
    DependencyKind.CLOCK: 0,
    DependencyKind.RESET: 1,
    DependencyKind.POWER_DOMAIN: 2,
    DependencyKind.DMA: 3,
    DependencyKind.IOMMU: 4,
    DependencyKind.INTERRUPT: 5,
}


@dataclass(frozen=True)
class DependencyViewWarning:
    code: str
    message: str
    consumer_dt_path: str | None = None
    provider_dt_path: str | None = None
    runtime_irq: int | None = None
    source_path: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.code, "DependencyViewWarning.code")
        _validate_non_empty(self.message, "DependencyViewWarning.message")
        _validate_optional_absolute_path(
            self.consumer_dt_path,
            "DependencyViewWarning.consumer_dt_path",
        )
        _validate_optional_absolute_path(
            self.provider_dt_path,
            "DependencyViewWarning.provider_dt_path",
        )
        if self.runtime_irq is not None:
            _validate_non_negative_int(
                self.runtime_irq,
                "DependencyViewWarning.runtime_irq",
            )
        _validate_optional_absolute_path(
            self.source_path,
            "DependencyViewWarning.source_path",
        )


@dataclass(frozen=True)
class DeviceDependency:
    static_reference: DependencyReference
    interrupt_correlation: InterruptCorrelation | None = None
    warnings: tuple[DependencyViewWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.static_reference, DependencyReference):
            raise TypeError(
                "DeviceDependency.static_reference must be DependencyReference"
            )

        if self.interrupt_correlation is not None:
            if not isinstance(self.interrupt_correlation, InterruptCorrelation):
                raise TypeError(
                    "DeviceDependency.interrupt_correlation must be "
                    "InterruptCorrelation"
                )
            if self.static_reference.kind != DependencyKind.INTERRUPT:
                raise ValueError(
                    "DeviceDependency.interrupt_correlation requires an "
                    "interrupt dependency"
                )
            if _dependency_key(self.static_reference) != _dependency_key(
                self.interrupt_correlation.dependency
            ):
                raise ValueError(
                    "DeviceDependency.interrupt_correlation must describe the "
                    "same dependency reference"
                )

        warnings = tuple(self.warnings)
        for warning in warnings:
            if not isinstance(warning, DependencyViewWarning):
                raise TypeError(
                    "DeviceDependency.warnings must be DependencyViewWarning"
                )
        object.__setattr__(self, "warnings", warnings)

    @property
    def kind(self) -> DependencyKind:
        return self.static_reference.kind

    @property
    def consumer_dt_path(self) -> str:
        return self.static_reference.consumer_dt_path

    @property
    def provider_dt_path(self) -> str | None:
        return self.static_reference.provider_dt_path

    @property
    def entry_index(self) -> int:
        return self.static_reference.entry_index

    @property
    def name(self) -> str | None:
        return self.static_reference.name

    @property
    def source_property(self) -> str | None:
        return self.static_reference.source_property

    @property
    def resolution(self) -> DependencyResolution:
        return self.static_reference.resolution

    @property
    def interrupt_resolution(self) -> InterruptCorrelationResolution | None:
        if self.interrupt_correlation is None:
            return None
        return self.interrupt_correlation.resolution

    @property
    def runtime_interrupt(self) -> RuntimeInterrupt | None:
        if self.interrupt_correlation is None:
            return None
        return self.interrupt_correlation.runtime_interrupt

    @property
    def interrupt_warnings(self) -> tuple[InterruptCorrelationWarning, ...]:
        if self.interrupt_correlation is None:
            return ()
        return self.interrupt_correlation.warnings


@dataclass(frozen=True)
class DeviceDependencyView:
    dt_node_path: str
    dependencies: tuple[DeviceDependency, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_absolute_path(self.dt_node_path, "DeviceDependencyView.dt_node_path")
        dependencies = tuple(self.dependencies)
        for dependency in dependencies:
            if not isinstance(dependency, DeviceDependency):
                raise TypeError(
                    "DeviceDependencyView.dependencies must be DeviceDependency"
                )
            if dependency.consumer_dt_path != self.dt_node_path:
                raise ValueError(
                    "DeviceDependencyView.dependencies must belong to dt_node_path"
                )
        object.__setattr__(self, "dependencies", dependencies)

    def dependencies_by_kind(
        self,
        kind: DependencyKind,
    ) -> tuple[DeviceDependency, ...]:
        if not isinstance(kind, DependencyKind):
            kind = DependencyKind(kind)
        return tuple(
            dependency
            for dependency in self.dependencies
            if dependency.kind == kind
        )


@dataclass(frozen=True)
class DependencyViewReport:
    devices: tuple[DeviceDependencyView, ...] = field(default_factory=tuple)
    warnings: tuple[DependencyViewWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        devices = tuple(self.devices)
        for device in devices:
            if not isinstance(device, DeviceDependencyView):
                raise TypeError(
                    "DependencyViewReport.devices must be DeviceDependencyView"
                )
        warnings = tuple(self.warnings)
        for warning in warnings:
            if not isinstance(warning, DependencyViewWarning):
                raise TypeError(
                    "DependencyViewReport.warnings must be DependencyViewWarning"
                )
        object.__setattr__(self, "devices", devices)
        object.__setattr__(self, "warnings", warnings)

    @property
    def dependencies(self) -> tuple[DeviceDependency, ...]:
        return tuple(
            dependency
            for device in self.devices
            for dependency in device.dependencies
        )


class DependencyViewBuilder:
    def build(
        self,
        *,
        dependencies: tuple[DependencyReference, ...],
        interrupt_correlations: tuple[InterruptCorrelation, ...] = (),
    ) -> DependencyViewReport:
        dependency_tuple = tuple(dependencies)
        correlation_index = _index_interrupt_correlations(interrupt_correlations)
        warnings: list[DependencyViewWarning] = []

        grouped: dict[str, list[DeviceDependency]] = {}
        for reference in sorted(dependency_tuple, key=_reference_sort_key):
            correlation = None
            if reference.kind == DependencyKind.INTERRUPT:
                matches = correlation_index.pop(_dependency_key(reference), ())
                if len(matches) == 1:
                    correlation = matches[0]
                elif len(matches) > 1:
                    warnings.append(
                        DependencyViewWarning(
                            code="INTERRUPT_CORRELATION_DUPLICATE_FOR_DEPENDENCY",
                            consumer_dt_path=reference.consumer_dt_path,
                            provider_dt_path=reference.provider_dt_path,
                            source_path=_reference_source_path(reference),
                            message=(
                                "Multiple interrupt correlations matched the "
                                "same dependency reference"
                            ),
                        )
                    )

            dependency = DeviceDependency(
                static_reference=reference,
                interrupt_correlation=correlation,
            )
            grouped.setdefault(reference.consumer_dt_path, []).append(dependency)

        return DependencyViewReport(
            devices=tuple(
                DeviceDependencyView(
                    dt_node_path=dt_node_path,
                    dependencies=tuple(grouped[dt_node_path]),
                )
                for dt_node_path in sorted(grouped)
            ),
            warnings=(
                *warnings,
                *_unmatched_correlation_warnings(correlation_index),
            ),
        )


def _index_interrupt_correlations(
    correlations: tuple[InterruptCorrelation, ...],
) -> dict[tuple[object, ...], tuple[InterruptCorrelation, ...]]:
    indexed: dict[tuple[object, ...], list[InterruptCorrelation]] = {}
    for correlation in tuple(correlations):
        if not isinstance(correlation, InterruptCorrelation):
            raise TypeError("interrupt_correlations must be InterruptCorrelation")
        indexed.setdefault(_dependency_key(correlation.dependency), []).append(
            correlation
        )
    return {key: tuple(value) for key, value in indexed.items()}


def _unmatched_correlation_warnings(
    correlation_index: dict[tuple[object, ...], tuple[InterruptCorrelation, ...]],
) -> tuple[DependencyViewWarning, ...]:
    warnings: list[DependencyViewWarning] = []
    for correlations in correlation_index.values():
        for correlation in correlations:
            dependency = correlation.dependency
            warnings.append(
                DependencyViewWarning(
                    code="INTERRUPT_CORRELATION_WITHOUT_DEPENDENCY",
                    consumer_dt_path=dependency.consumer_dt_path,
                    provider_dt_path=dependency.provider_dt_path,
                    source_path=_reference_source_path(dependency),
                    message=(
                        "Interrupt correlation did not match any dependency "
                        "reference in the dependency view input"
                    ),
                )
            )
    return tuple(warnings)


def _reference_sort_key(
    reference: DependencyReference,
) -> tuple[str, int, str, int, str]:
    return (
        reference.consumer_dt_path,
        _KIND_ORDER[reference.kind],
        reference.source_property or "",
        reference.entry_index,
        reference.name or "",
    )


def _dependency_key(reference: DependencyReference) -> tuple[object, ...]:
    return (
        reference.kind,
        reference.consumer_dt_path,
        reference.provider_dt_path,
        reference.provider_phandle,
        reference.entry_index,
        reference.name,
        reference.specifier_cells,
        reference.source_property,
        reference.resolution,
    )


def _reference_source_path(reference: DependencyReference) -> str | None:
    for evidence in reference.evidence:
        if evidence.source_path is not None:
            return evidence.source_path
    return None


def _validate_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _validate_absolute_path(value: str, field_name: str) -> None:
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_optional_absolute_path(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_absolute_path(value, field_name)


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
