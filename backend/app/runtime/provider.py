from __future__ import annotations

from typing import Protocol

from app.runtime.model import LinuxRuntimeSnapshot


class RuntimeProvider(Protocol):
    def collect(self) -> LinuxRuntimeSnapshot:
        """Collect one point-in-time runtime snapshot."""
        ...
