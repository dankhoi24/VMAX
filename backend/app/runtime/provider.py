from __future__ import annotations

from typing import Protocol

from app.runtime.model import (
    IomemRegion,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeSystemInfo,
)


class RuntimeProvider(Protocol):
    def collect_system_info(self) -> RuntimeSystemInfo:
        """Collect runtime host and kernel metadata."""
        ...

    def collect_devices(self) -> tuple[RuntimeDevice, ...]:
        """Collect runtime devices without forcing unrelated runtime data reads."""
        ...

    def collect_drivers(self) -> tuple[RuntimeDriver, ...]:
        """Collect runtime drivers without forcing unrelated runtime data reads."""
        ...

    def collect_iomem(self) -> tuple[IomemRegion, ...]:
        """Collect the runtime /proc/iomem hierarchy."""
        ...
