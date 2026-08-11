from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.services.devicetree_state import DeviceTreeState


router = APIRouter(prefix="/api/v1", tags=["devicetree"])


def get_devicetree_state(request: Request) -> DeviceTreeState:
    return request.app.state.devicetree_state


@router.get("/metadata")
def get_metadata(
    state: DeviceTreeState = Depends(get_devicetree_state),
) -> dict[str, object]:
    return state.metadata()


@router.get("/devicetree")
def get_devicetree(
    state: DeviceTreeState = Depends(get_devicetree_state),
) -> dict[str, object]:
    result = state.collect()
    if result.tree is None:
        raise HTTPException(
            status_code=422,
            detail={
                "source": result.source,
                "warnings": list(result.warnings),
                "errors": list(result.errors),
            },
        )

    return result.tree.to_dict()
