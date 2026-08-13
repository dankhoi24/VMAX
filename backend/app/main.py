from __future__ import annotations

from fastapi import FastAPI

from app.addressing import AddressingAnalyzer
from app.api.addressing import router as addressing_router
from app.api.devicetree import router as devicetree_router
from app.services.devicetree_state import DeviceTreeState


def create_app(
    devicetree_state: DeviceTreeState | None = None,
    addressing_analyzer: AddressingAnalyzer | None = None,
) -> FastAPI:
    app = FastAPI(title="VMAX Hardware Explorer", version="0.1.0")
    app.state.devicetree_state = (
        devicetree_state
        if devicetree_state is not None
        else DeviceTreeState.from_environment()
    )
    app.state.addressing_analyzer = addressing_analyzer or AddressingAnalyzer()
    app.include_router(devicetree_router)
    app.include_router(addressing_router)
    return app


app = create_app()
