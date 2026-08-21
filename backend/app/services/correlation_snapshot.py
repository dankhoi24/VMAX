from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.addressing import AddressingAnalyzer
from app.correlation import CorrelationReport, CorrelationService, CorrelationWarning
from app.model.addressing import AddressingWarning
from app.model.devicetree import ParseResult
from app.runtime import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeProvider,
    RuntimeWarning,
)
from app.services.devicetree_state import DeviceTreeState


@dataclass(frozen=True)
class CorrelationSourceError(Exception):
    source: str | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class CorrelationSnapshotService:
    def __init__(
        self,
        *,
        devicetree_state: DeviceTreeState,
        addressing_analyzer: AddressingAnalyzer,
        runtime_provider: RuntimeProvider,
        correlation_service: CorrelationService,
    ) -> None:
        self._devicetree_state = devicetree_state
        self._addressing_analyzer = addressing_analyzer
        self._runtime_provider = runtime_provider
        self._correlation_service = correlation_service

    def build_report(self) -> CorrelationReport:
        parse_result = self._devicetree_state.collect()
        if parse_result.tree is None:
            raise CorrelationSourceError(
                source=parse_result.source,
                warnings=parse_result.warnings,
                errors=parse_result.errors,
            )

        addressing_report = self._addressing_analyzer.analyze(parse_result.tree)
        devices = self._runtime_provider.collect_devices()
        drivers = self._runtime_provider.collect_drivers()
        iomem = self._runtime_provider.collect_iomem()

        correlation_report = self._correlation_service.correlate(
            tree=parse_result.tree,
            addressing=addressing_report,
            devices=devices.data,
            drivers=drivers.data,
            iomem=iomem.data,
            devices_complete=_devices_source_complete(devices),
            drivers_complete=_drivers_source_complete(drivers),
            iomem_complete=_iomem_source_complete(iomem),
        )

        warnings = (
            _parse_warnings_to_correlation_warnings(parse_result)
            + _addressing_warnings_to_correlation_warnings(
                addressing_report.warnings
            )
            + _runtime_warnings_to_correlation_warnings(devices.warnings)
            + _runtime_warnings_to_correlation_warnings(drivers.warnings)
            + _runtime_warnings_to_correlation_warnings(iomem.warnings)
            + correlation_report.warnings
        )

        return CorrelationReport(
            devices=correlation_report.devices,
            warnings=warnings,
        )


def _parse_warnings_to_correlation_warnings(
    result: ParseResult,
) -> tuple[CorrelationWarning, ...]:
    return tuple(
        CorrelationWarning(
            code="DT_PARSE_WARNING",
            message=warning,
        )
        for warning in result.warnings
    )


def _addressing_warnings_to_correlation_warnings(
    warnings: tuple[AddressingWarning, ...],
) -> tuple[CorrelationWarning, ...]:
    return tuple(
        CorrelationWarning(
            code=warning.code,
            message=warning.message,
            dt_node_path=warning.node_path,
        )
        for warning in warnings
    )


def _runtime_warnings_to_correlation_warnings(
    warnings: tuple[RuntimeWarning, ...],
) -> tuple[CorrelationWarning, ...]:
    return tuple(
        CorrelationWarning(
            code=warning.code,
            message=warning.message,
            source_path=warning.source_path,
        )
        for warning in warnings
    )


def _iomem_source_complete(
    collection: RuntimeCollection[tuple[IomemRegion, ...]],
) -> bool:
    incomplete_codes = {
        "PROC_IOMEM_READ_FAILED",
        "PROC_IOMEM_ADDRESSES_REDACTED",
        "PROC_IOMEM_PARSE_FAILED",
    }
    return not any(
        warning.code in incomplete_codes
        for warning in collection.warnings
    )


def _devices_source_complete(
    collection: RuntimeCollection[tuple[RuntimeDevice, ...]],
) -> bool:
    return _source_complete(
        collection,
        incomplete_codes={
            "SYSFS_PLATFORM_DEVICES_READ_FAILED",
            "SYSFS_PLATFORM_DEVICE_READ_FAILED",
            "SYSFS_PLATFORM_DEVICE_OF_NODE_READ_FAILED",
        },
    )


def _drivers_source_complete(
    collection: RuntimeCollection[tuple[RuntimeDriver, ...]],
) -> bool:
    return _source_complete(
        collection,
        incomplete_codes={
            "SYSFS_PLATFORM_DRIVERS_READ_FAILED",
            "SYSFS_PLATFORM_DRIVER_READ_FAILED",
        },
    )


def _source_complete(
    collection: RuntimeCollection[Any],
    *,
    incomplete_codes: set[str],
) -> bool:
    return not any(
        warning.code in incomplete_codes
        for warning in collection.warnings
    )
