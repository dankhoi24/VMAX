from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.addressing import AddressingAnalyzer
from app.api.schemas.addressing import (
    AddressingReportResponse,
    addressing_report_to_response,
)
from app.api.schemas.devicetree import ErrorResponse, ParseErrorDetail
from app.services.devicetree_state import DeviceTreeState


router = APIRouter(prefix="/api/v1", tags=["addressing"])


def get_devicetree_state(request: Request) -> DeviceTreeState:
    return request.app.state.devicetree_state


def get_addressing_analyzer(request: Request) -> AddressingAnalyzer:
    return request.app.state.addressing_analyzer


@router.get(
    "/addressing",
    response_model=AddressingReportResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_addressing(
    state: DeviceTreeState = Depends(get_devicetree_state),
    analyzer: AddressingAnalyzer = Depends(get_addressing_analyzer),
) -> AddressingReportResponse:
    result = state.collect()
    if result.tree is None:
        detail = ParseErrorDetail(
            source=result.source,
            warnings=list(result.warnings),
            errors=list(result.errors),
        )
        raise HTTPException(
            status_code=422,
            detail=detail.model_dump(),
        )

    return addressing_report_to_response(analyzer.analyze(result.tree))
