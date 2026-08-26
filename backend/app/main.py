from __future__ import annotations

from fastapi import FastAPI

from app.addressing import AddressingAnalyzer
from app.api.addressing import router as addressing_router
from app.api.correlation import router as correlation_router
from app.api.dependency import router as dependency_router
from app.api.devicetree import router as devicetree_router
from app.api.runtime import router as runtime_router
from app.correlation import CorrelationService
from app.dependency import DependencyViewBuilder, DeviceTreeDependencyExtractor
from app.interrupts import InterruptCorrelationService
from app.runtime import RuntimeProvider
from app.runtime.config import runtime_provider_from_environment
from app.services.devicetree_state import DeviceTreeState


def create_app(
    devicetree_state: DeviceTreeState | None = None,
    addressing_analyzer: AddressingAnalyzer | None = None,
    runtime_provider: RuntimeProvider | None = None,
    correlation_service: CorrelationService | None = None,
    dependency_extractor: DeviceTreeDependencyExtractor | None = None,
    interrupt_correlation_service: InterruptCorrelationService | None = None,
    dependency_view_builder: DependencyViewBuilder | None = None,
) -> FastAPI:
    app = FastAPI(title="VMAX Hardware Explorer", version="0.4.0")
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
    app.state.dependency_extractor = (
        dependency_extractor
        if dependency_extractor is not None
        else DeviceTreeDependencyExtractor()
    )
    app.state.interrupt_correlation_service = (
        interrupt_correlation_service
        if interrupt_correlation_service is not None
        else InterruptCorrelationService()
    )
    app.state.dependency_view_builder = (
        dependency_view_builder
        if dependency_view_builder is not None
        else DependencyViewBuilder()
    )
    app.include_router(devicetree_router)
    app.include_router(addressing_router)
    app.include_router(runtime_router)
    app.include_router(correlation_router)
    app.include_router(dependency_router)
    return app


app = create_app()
