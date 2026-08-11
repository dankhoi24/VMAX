from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas.devicetree import (
    DeviceTreeResponse,
    ErrorResponse,
    MetadataResponse,
    ParseErrorDetail,
)
from app.services.devicetree_state import DeviceTreeState


router = APIRouter(prefix="/api/v1", tags=["devicetree"])


def get_devicetree_state(request: Request) -> DeviceTreeState:
    return request.app.state.devicetree_state


@router.get("/metadata", response_model=MetadataResponse)
def get_metadata(
    state: DeviceTreeState = Depends(get_devicetree_state),
) -> MetadataResponse:
    return MetadataResponse.model_validate(state.metadata())


@router.get(
    "/devicetree",
    response_model=DeviceTreeResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_devicetree(
    state: DeviceTreeState = Depends(get_devicetree_state),
) -> DeviceTreeResponse:
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

    return DeviceTreeResponse.model_validate(result.tree.to_dict())
