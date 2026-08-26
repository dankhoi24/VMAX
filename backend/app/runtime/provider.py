from __future__ import annotations

from typing import Protocol

from app.runtime.model import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeInterrupt,
    RuntimeSystemInfo,
)


class RuntimeProvider(Protocol):
    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        """Collect runtime host and kernel metadata."""
        ...

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        """Collect runtime devices without forcing unrelated runtime data reads."""
        ...

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        """Collect runtime drivers without forcing unrelated runtime data reads."""
        ...

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        """Collect the runtime /proc/iomem hierarchy."""
        ...

    def collect_interrupts(self) -> RuntimeCollection[tuple[RuntimeInterrupt, ...]]:
        """Collect the runtime Linux interrupt inventory."""
        ...
