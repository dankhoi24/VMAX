from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.schemas.runtime import (
    RuntimeDeviceCollectionResponse,
    RuntimeDriverCollectionResponse,
    RuntimeIomemCollectionResponse,
    RuntimeMetadataCollectionResponse,
    RuntimeInterruptCollectionResponse,
    runtime_device_collection_to_response,
    runtime_driver_collection_to_response,
    runtime_iomem_collection_to_response,
    runtime_interrupt_collection_to_response,
    runtime_metadata_collection_to_response,
)
from app.runtime import RuntimeProvider


router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


def get_runtime_provider(request: Request) -> RuntimeProvider:
    return request.app.state.runtime_provider


@router.get("/metadata", response_model=RuntimeMetadataCollectionResponse)
def get_runtime_metadata(
    provider: RuntimeProvider = Depends(get_runtime_provider),
) -> RuntimeMetadataCollectionResponse:
    return runtime_metadata_collection_to_response(provider.collect_system_info())


@router.get("/devices", response_model=RuntimeDeviceCollectionResponse)
def get_runtime_devices(
    provider: RuntimeProvider = Depends(get_runtime_provider),
) -> RuntimeDeviceCollectionResponse:
    return runtime_device_collection_to_response(provider.collect_devices())


@router.get("/drivers", response_model=RuntimeDriverCollectionResponse)
def get_runtime_drivers(
    provider: RuntimeProvider = Depends(get_runtime_provider),
) -> RuntimeDriverCollectionResponse:
    return runtime_driver_collection_to_response(provider.collect_drivers())


@router.get("/iomem", response_model=RuntimeIomemCollectionResponse)
def get_runtime_iomem(
    provider: RuntimeProvider = Depends(get_runtime_provider),
) -> RuntimeIomemCollectionResponse:
    return runtime_iomem_collection_to_response(provider.collect_iomem())


@router.get("/interrupts", response_model=RuntimeInterruptCollectionResponse)
def get_runtime_interrupts(
    provider: RuntimeProvider = Depends(get_runtime_provider),
) -> RuntimeInterruptCollectionResponse:
    return runtime_interrupt_collection_to_response(provider.collect_interrupts())
