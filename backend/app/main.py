from __future__ import annotations

from fastapi import FastAPI

from app.addressing import AddressingAnalyzer
from app.api.addressing import router as addressing_router
from app.api.correlation import router as correlation_router
from app.api.devicetree import router as devicetree_router
from app.api.runtime import router as runtime_router
from app.correlation import CorrelationService
from app.runtime import RuntimeProvider
from app.runtime.config import runtime_provider_from_environment
from app.services.devicetree_state import DeviceTreeState


def create_app(
    devicetree_state: DeviceTreeState | None = None,
    addressing_analyzer: AddressingAnalyzer | None = None,
    runtime_provider: RuntimeProvider | None = None,
    correlation_service: CorrelationService | None = None,
) -> FastAPI:
    app = FastAPI(title="VMAX Hardware Explorer", version="0.3.0")
    app.state.devicetree_state = (
        devicetree_state
        if devicetree_state is not None
        else DeviceTreeState.from_environment()
    )
    app.state.addressing_analyzer = addressing_analyzer or AddressingAnalyzer()
    app.state.runtime_provider = (
        runtime_provider
        if runtime_provider is not None
        else runtime_provider_from_environment()
    )
    app.state.correlation_service = correlation_service or CorrelationService()
    app.include_router(devicetree_router)
    app.include_router(addressing_router)
    app.include_router(runtime_router)
    app.include_router(correlation_router)
    return app


app = create_app()
