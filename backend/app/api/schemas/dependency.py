from __future__ import annotations

from pydantic import BaseModel

from app.dependency import (
    DependencyEvidence,
    DependencyEvidenceKind,
    DependencyKind,
    DependencyResolution,
    DependencyViewReport,
    DependencyViewWarning,
    DeviceDependency,
    DeviceDependencyView,
)
from app.interrupts import (
    InterruptCorrelationResolution,
    InterruptCorrelationWarning,
    InterruptMatchMethod,
)
from app.runtime import RuntimeInterrupt


class DependencyWarningResponse(BaseModel):
    code: str
    message: str
    consumer_dt_path: str | None = None
    provider_dt_path: str | None = None
    source_path: str | None = None


class DependencyEvidenceResponse(BaseModel):
    kind: DependencyEvidenceKind
    source: str
    source_path: str | None = None
    message: str | None = None


class DependencyRuntimeInterruptResponse(BaseModel):
    irq: int
    counts: list[int]
    controller: str | None = None
    hardware_irq: int | None = None
    trigger: str | None = None
    actions: list[str]
    total_count: int
    source_path: str


class DeviceDependencyResponse(BaseModel):
    kind: DependencyKind
    consumer_dt_path: str
    provider_dt_path: str | None
    provider_phandle: int | None
    entry_index: int
    name: str | None
    specifier_cells: list[int]
    source_property: str | None
    static_resolution: DependencyResolution
    evidence: list[DependencyEvidenceResponse]
    interrupt_resolution: InterruptCorrelationResolution | None = None
    interrupt_match_method: InterruptMatchMethod | None = None
    runtime_interrupt: DependencyRuntimeInterruptResponse | None = None
    runtime_candidates: list[DependencyRuntimeInterruptResponse]
    interrupt_warnings: list[DependencyWarningResponse]


class DeviceDependencyViewResponse(BaseModel):
    dt_node_path: str
    dependencies: list[DeviceDependencyResponse]


class DependencyDeviceCollectionResponse(BaseModel):
    data: list[DeviceDependencyViewResponse]
    warnings: list[DependencyWarningResponse]


def dependency_report_to_response(
    report: DependencyViewReport,
) -> DependencyDeviceCollectionResponse:
    return DependencyDeviceCollectionResponse(
        data=[_device_view_to_response(device) for device in report.devices],
        warnings=[_warning_to_response(warning) for warning in report.warnings],
    )


def _device_view_to_response(
    device: DeviceDependencyView,
) -> DeviceDependencyViewResponse:
    return DeviceDependencyViewResponse(
        dt_node_path=device.dt_node_path,
        dependencies=[
            _device_dependency_to_response(dependency)
            for dependency in device.dependencies
        ],
    )


def _device_dependency_to_response(
    dependency: DeviceDependency,
) -> DeviceDependencyResponse:
    reference = dependency.static_reference
    interrupt = dependency.interrupt_correlation
    return DeviceDependencyResponse(
        kind=dependency.kind,
        consumer_dt_path=dependency.consumer_dt_path,
        provider_dt_path=dependency.provider_dt_path,
        provider_phandle=reference.provider_phandle,
        entry_index=dependency.entry_index,
        name=dependency.name,
        specifier_cells=list(reference.specifier_cells),
        source_property=dependency.source_property,
        static_resolution=dependency.resolution,
        evidence=[
            _evidence_to_response(evidence)
            for evidence in reference.evidence
        ],
        interrupt_resolution=(
            None if interrupt is None else interrupt.resolution
        ),
        interrupt_match_method=(
            None if interrupt is None else interrupt.match_method
        ),
        runtime_interrupt=_runtime_interrupt_to_response(
            dependency.runtime_interrupt
        ),
        runtime_candidates=(
            []
            if interrupt is None
            else [
                _runtime_interrupt_required_to_response(candidate)
                for candidate in interrupt.runtime_candidates
            ]
        ),
        interrupt_warnings=[
            _interrupt_warning_to_response(warning)
            for warning in dependency.interrupt_warnings
        ],
    )


def _evidence_to_response(
    evidence: DependencyEvidence,
) -> DependencyEvidenceResponse:
    return DependencyEvidenceResponse(
        kind=evidence.kind,
        source=evidence.source,
        source_path=evidence.source_path,
        message=evidence.message,
    )


def _runtime_interrupt_to_response(
    interrupt: RuntimeInterrupt | None,
) -> DependencyRuntimeInterruptResponse | None:
    if interrupt is None:
        return None

    return _runtime_interrupt_required_to_response(interrupt)


def _runtime_interrupt_required_to_response(
    interrupt: RuntimeInterrupt,
) -> DependencyRuntimeInterruptResponse:
    return DependencyRuntimeInterruptResponse(
        irq=interrupt.irq,
        counts=list(interrupt.counts),
        controller=interrupt.controller,
        hardware_irq=interrupt.hardware_irq,
        trigger=interrupt.trigger,
        actions=list(interrupt.actions),
        total_count=interrupt.total_count,
        source_path=interrupt.source_path,
    )


def _warning_to_response(
    warning: DependencyViewWarning,
) -> DependencyWarningResponse:
    return DependencyWarningResponse(
        code=warning.code,
        message=warning.message,
        consumer_dt_path=warning.consumer_dt_path,
        provider_dt_path=warning.provider_dt_path,
        source_path=warning.source_path,
    )


def _interrupt_warning_to_response(
    warning: InterruptCorrelationWarning,
) -> DependencyWarningResponse:
    return DependencyWarningResponse(
        code=warning.code,
        message=warning.message,
        consumer_dt_path=warning.consumer_dt_path,
        provider_dt_path=warning.provider_dt_path,
        source_path=warning.source_path,
    )
