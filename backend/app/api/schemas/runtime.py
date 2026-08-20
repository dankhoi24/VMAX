from __future__ import annotations

from pydantic import BaseModel

from app.runtime.model import (
    IomemRegion,
    MetadataValue,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeResource,
    RuntimeSystemInfo,
    RuntimeWarning,
)


class RuntimeWarningResponse(BaseModel):
    code: str
    message: str
    source_path: str | None = None


class RuntimeSystemInfoResponse(BaseModel):
    hostname: str | None = None
    kernel_name: str | None = None
    kernel_release: str | None = None
    kernel_version: str | None = None
    machine: str | None = None
    architecture: str | None = None
    cmdline: str | None = None


class RuntimeResourceResponse(BaseModel):
    index: int
    start: int
    end: int
    flags: int
    flag_names: list[str]
    name: str | None = None
    size: int


class RuntimeDeviceResponse(BaseModel):
    name: str
    sysfs_path: str
    bus: str
    driver_name: str | None = None
    driver_path: str | None = None
    of_node_sysfs_path: str | None = None
    subsystem_path: str | None = None
    modalias: str | None = None
    resources: list[RuntimeResourceResponse]
    metadata: list[tuple[str, MetadataValue]]


class RuntimeDriverResponse(BaseModel):
    name: str
    sysfs_path: str
    bus: str
    module_name: str | None = None
    bound_device_paths: list[str]
    metadata: list[tuple[str, MetadataValue]]


class IomemRegionResponse(BaseModel):
    start: int
    end: int
    name: str
    children: list["IomemRegionResponse"]
    size: int


class RuntimeMetadataCollectionResponse(BaseModel):
    data: RuntimeSystemInfoResponse
    warnings: list[RuntimeWarningResponse]


class RuntimeDeviceCollectionResponse(BaseModel):
    data: list[RuntimeDeviceResponse]
    warnings: list[RuntimeWarningResponse]


class RuntimeDriverCollectionResponse(BaseModel):
    data: list[RuntimeDriverResponse]
    warnings: list[RuntimeWarningResponse]


class RuntimeIomemCollectionResponse(BaseModel):
    data: list[IomemRegionResponse]
    warnings: list[RuntimeWarningResponse]


def runtime_metadata_collection_to_response(
    collection: RuntimeCollection[RuntimeSystemInfo],
) -> RuntimeMetadataCollectionResponse:
    return RuntimeMetadataCollectionResponse(
        data=_system_info_to_response(collection.data),
        warnings=_warnings_to_response(collection.warnings),
    )


def runtime_device_collection_to_response(
    collection: RuntimeCollection[tuple[RuntimeDevice, ...]],
) -> RuntimeDeviceCollectionResponse:
    return RuntimeDeviceCollectionResponse(
        data=[_device_to_response(device) for device in collection.data],
        warnings=_warnings_to_response(collection.warnings),
    )


def runtime_driver_collection_to_response(
    collection: RuntimeCollection[tuple[RuntimeDriver, ...]],
) -> RuntimeDriverCollectionResponse:
    return RuntimeDriverCollectionResponse(
        data=[_driver_to_response(driver) for driver in collection.data],
        warnings=_warnings_to_response(collection.warnings),
    )


def runtime_iomem_collection_to_response(
    collection: RuntimeCollection[tuple[IomemRegion, ...]],
) -> RuntimeIomemCollectionResponse:
    return RuntimeIomemCollectionResponse(
        data=[_iomem_region_to_response(region) for region in collection.data],
        warnings=_warnings_to_response(collection.warnings),
    )


def _system_info_to_response(info: RuntimeSystemInfo) -> RuntimeSystemInfoResponse:
    return RuntimeSystemInfoResponse(
        hostname=info.hostname,
        kernel_name=info.kernel_name,
        kernel_release=info.kernel_release,
        kernel_version=info.kernel_version,
        machine=info.machine,
        architecture=info.architecture,
        cmdline=info.cmdline,
    )


def _device_to_response(device: RuntimeDevice) -> RuntimeDeviceResponse:
    return RuntimeDeviceResponse(
        name=device.name,
        sysfs_path=device.sysfs_path,
        bus=device.bus,
        driver_name=device.driver_name,
        driver_path=device.driver_path,
        of_node_sysfs_path=device.of_node_sysfs_path,
        subsystem_path=device.subsystem_path,
        modalias=device.modalias,
        resources=[_resource_to_response(resource) for resource in device.resources],
        metadata=list(device.metadata),
    )


def _resource_to_response(resource: RuntimeResource) -> RuntimeResourceResponse:
    return RuntimeResourceResponse(
        index=resource.index,
        start=resource.start,
        end=resource.end,
        flags=resource.flags,
        flag_names=list(resource.flag_names),
        name=resource.name,
        size=resource.size,
    )


def _driver_to_response(driver: RuntimeDriver) -> RuntimeDriverResponse:
    return RuntimeDriverResponse(
        name=driver.name,
        sysfs_path=driver.sysfs_path,
        bus=driver.bus,
        module_name=driver.module_name,
        bound_device_paths=list(driver.bound_device_paths),
        metadata=list(driver.metadata),
    )


def _iomem_region_to_response(region: IomemRegion) -> IomemRegionResponse:
    return IomemRegionResponse(
        start=region.start,
        end=region.end,
        name=region.name,
        children=[_iomem_region_to_response(child) for child in region.children],
        size=region.size,
    )


def _warnings_to_response(
    warnings: tuple[RuntimeWarning, ...],
) -> list[RuntimeWarningResponse]:
    return [_warning_to_response(warning) for warning in warnings]


def _warning_to_response(warning: RuntimeWarning) -> RuntimeWarningResponse:
    return RuntimeWarningResponse(
        code=warning.code,
        message=warning.message,
        source_path=warning.source_path,
    )
