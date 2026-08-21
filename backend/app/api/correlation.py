from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.addressing import AddressingAnalyzer
from app.api.schemas.correlation import (
    CorrelationDeviceCollectionResponse,
    correlation_report_to_response,
)
from app.api.schemas.devicetree import ErrorResponse, ParseErrorDetail
from app.correlation import CorrelationService
from app.runtime import RuntimeProvider
from app.services.correlation_snapshot import (
    CorrelationSnapshotService,
    CorrelationSourceError,
)
from app.services.devicetree_state import DeviceTreeState


router = APIRouter(prefix="/api/v1/correlation", tags=["correlation"])


def get_correlation_snapshot_service(
    request: Request,
) -> CorrelationSnapshotService:
    state: DeviceTreeState = request.app.state.devicetree_state
    analyzer: AddressingAnalyzer = request.app.state.addressing_analyzer
    runtime_provider: RuntimeProvider = request.app.state.runtime_provider
    correlation_service: CorrelationService = request.app.state.correlation_service

    return CorrelationSnapshotService(
        devicetree_state=state,
        addressing_analyzer=analyzer,
        runtime_provider=runtime_provider,
        correlation_service=correlation_service,
    )


@router.get(
    "/devices",
    response_model=CorrelationDeviceCollectionResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_correlation_devices(
    snapshot_service: CorrelationSnapshotService = Depends(
        get_correlation_snapshot_service
    ),
) -> CorrelationDeviceCollectionResponse:
    try:
        report = snapshot_service.build_report()
    except CorrelationSourceError as exc:
        detail = ParseErrorDetail(
            source=exc.source,
            warnings=list(exc.warnings),
            errors=list(exc.errors),
        )
        raise HTTPException(
            status_code=422,
            detail=detail.model_dump(),
        ) from exc

    return correlation_report_to_response(report)
