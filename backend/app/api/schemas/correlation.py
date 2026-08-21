from __future__ import annotations

from pydantic import BaseModel

from app.correlation import (
    AddressCorrelation,
    AddressMatchType,
    CorrelatedDevice,
    CorrelationMatchMethod,
    CorrelationReport,
    CorrelationWarning,
    IomemCandidate,
)
from app.model.addressing import TranslatedAddressRange
from app.runtime import RuntimeDevice, RuntimeDriver


class CorrelationWarningResponse(BaseModel):
    code: str
    message: str
    dt_node_path: str | None = None
    runtime_device_path: str | None = None
    source_path: str | None = None


class CorrelatedRuntimeDeviceResponse(BaseModel):
    name: str
    sysfs_path: str
    bus: str
    driver_name: str | None = None
    driver_path: str | None = None
    of_node_sysfs_path: str | None = None


class CorrelatedRuntimeDriverResponse(BaseModel):
    name: str
    sysfs_path: str
    bus: str
    module_name: str | None = None


class StaticAddressRegionResponse(BaseModel):
    node_path: str
    bus_address: str
    cpu_start: str | None
    size: str | None
    cpu_end: str | None


class IomemCandidateResponse(BaseModel):
    start: str
    end: str
    name: str


class AddressCorrelationResponse(BaseModel):
    dt_start: str
    dt_end: str
    iomem_start: str | None
    iomem_end: str | None
    iomem_name: str | None
    match_type: AddressMatchType
    candidates: list[IomemCandidateResponse]


class CorrelatedDeviceResponse(BaseModel):
    dt_node_path: str | None
    runtime_device: CorrelatedRuntimeDeviceResponse | None
    runtime_driver: CorrelatedRuntimeDriverResponse | None
    static_regions: list[StaticAddressRegionResponse]
    address_matches: list[AddressCorrelationResponse]
    match_method: CorrelationMatchMethod
    warnings: list[CorrelationWarningResponse]


class CorrelationDeviceCollectionResponse(BaseModel):
    data: list[CorrelatedDeviceResponse]
    warnings: list[CorrelationWarningResponse]


def correlation_report_to_response(
    report: CorrelationReport,
) -> CorrelationDeviceCollectionResponse:
    return CorrelationDeviceCollectionResponse(
        data=[_correlated_device_to_response(device) for device in report.devices],
        warnings=[_warning_to_response(warning) for warning in report.warnings],
    )


def _correlated_device_to_response(
    device: CorrelatedDevice,
) -> CorrelatedDeviceResponse:
    return CorrelatedDeviceResponse(
        dt_node_path=device.dt_node_path,
        runtime_device=_runtime_device_to_response(device.runtime_device),
        runtime_driver=_runtime_driver_to_response(device.runtime_driver),
        static_regions=[
            _static_region_to_response(region)
            for region in device.static_regions
        ],
        address_matches=[
            _address_correlation_to_response(match)
            for match in device.address_matches
        ],
        match_method=device.match_method,
        warnings=[_warning_to_response(warning) for warning in device.warnings],
    )


def _runtime_device_to_response(
    device: RuntimeDevice | None,
) -> CorrelatedRuntimeDeviceResponse | None:
    if device is None:
        return None

    return CorrelatedRuntimeDeviceResponse(
        name=device.name,
        sysfs_path=device.sysfs_path,
        bus=device.bus,
        driver_name=device.driver_name,
        driver_path=device.driver_path,
        of_node_sysfs_path=device.of_node_sysfs_path,
    )


def _runtime_driver_to_response(
    driver: RuntimeDriver | None,
) -> CorrelatedRuntimeDriverResponse | None:
    if driver is None:
        return None

    return CorrelatedRuntimeDriverResponse(
        name=driver.name,
        sysfs_path=driver.sysfs_path,
        bus=driver.bus,
        module_name=driver.module_name,
    )


def _static_region_to_response(
    region: TranslatedAddressRange,
) -> StaticAddressRegionResponse:
    return StaticAddressRegionResponse(
        node_path=region.node_path,
        bus_address=_hex(region.bus_address),
        cpu_start=_hex(region.cpu_address),
        size=_hex(region.size),
        cpu_end=_hex(region.end),
    )


def _address_correlation_to_response(
    match: AddressCorrelation,
) -> AddressCorrelationResponse:
    return AddressCorrelationResponse(
        dt_start=_hex_required(match.dt_start),
        dt_end=_hex_required(match.dt_end),
        iomem_start=_hex(match.iomem_start),
        iomem_end=_hex(match.iomem_end),
        iomem_name=match.iomem_name,
        match_type=match.match_type,
        candidates=[
            _iomem_candidate_to_response(candidate)
            for candidate in match.candidates
        ],
    )


def _iomem_candidate_to_response(
    candidate: IomemCandidate,
) -> IomemCandidateResponse:
    return IomemCandidateResponse(
        start=_hex_required(candidate.start),
        end=_hex_required(candidate.end),
        name=candidate.name,
    )


def _warning_to_response(
    warning: CorrelationWarning,
) -> CorrelationWarningResponse:
    return CorrelationWarningResponse(
        code=warning.code,
        message=warning.message,
        dt_node_path=warning.dt_node_path,
        runtime_device_path=warning.runtime_device_path,
        source_path=warning.source_path,
    )


def _hex(value: int | None) -> str | None:
    if value is None:
        return None
    return _hex_required(value)


def _hex_required(value: int) -> str:
    return f"0x{value:x}"
