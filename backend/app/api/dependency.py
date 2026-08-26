from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas.dependency import (
    DependencyDeviceCollectionResponse,
    dependency_report_to_response,
)
from app.api.schemas.devicetree import ErrorResponse, ParseErrorDetail
from app.dependency import DependencyViewBuilder, DeviceTreeDependencyExtractor
from app.interrupts import InterruptCorrelationService
from app.runtime import RuntimeProvider
from app.services.dependency_snapshot import (
    DependencySnapshotService,
    DependencySourceError,
)
from app.services.devicetree_state import DeviceTreeState


router = APIRouter(prefix="/api/v1/dependencies", tags=["dependencies"])


def get_dependency_snapshot_service(
    request: Request,
) -> DependencySnapshotService:
    state: DeviceTreeState = request.app.state.devicetree_state
    runtime_provider: RuntimeProvider = request.app.state.runtime_provider
    dependency_extractor: DeviceTreeDependencyExtractor = (
        request.app.state.dependency_extractor
    )
    interrupt_correlation_service: InterruptCorrelationService = (
        request.app.state.interrupt_correlation_service
    )
    dependency_view_builder: DependencyViewBuilder = (
        request.app.state.dependency_view_builder
    )

    return DependencySnapshotService(
        devicetree_state=state,
        runtime_provider=runtime_provider,
        dependency_extractor=dependency_extractor,
        interrupt_correlation_service=interrupt_correlation_service,
        dependency_view_builder=dependency_view_builder,
    )


@router.get(
    "/devices",
    response_model=DependencyDeviceCollectionResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_dependency_devices(
    snapshot_service: DependencySnapshotService = Depends(
        get_dependency_snapshot_service
    ),
) -> DependencyDeviceCollectionResponse:
    try:
        report = snapshot_service.build_report()
    except DependencySourceError as exc:
        detail = ParseErrorDetail(
            source=exc.source,
            warnings=list(exc.warnings),
            errors=list(exc.errors),
        )
        raise HTTPException(
            status_code=422,
            detail=detail.model_dump(),
        ) from exc

    return dependency_report_to_response(report)
