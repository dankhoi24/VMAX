from __future__ import annotations

import os
from pathlib import Path

from app.runtime.model import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeSystemInfo,
)
from app.runtime.provider import RuntimeProvider


PathInput = str | os.PathLike[str]


class LocalLinuxRuntimeProvider(RuntimeProvider):
    def __init__(
        self,
        sysfs_root: PathInput = Path("/sys"),
        proc_root: PathInput = Path("/proc"),
    ) -> None:
        self._sysfs_root = _normalize_root(sysfs_root, "sysfs_root")
        self._proc_root = _normalize_root(proc_root, "proc_root")

    @property
    def sysfs_root(self) -> Path:
        return self._sysfs_root

    @property
    def proc_root(self) -> Path:
        return self._proc_root

    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        return RuntimeCollection(data=RuntimeSystemInfo())

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        return RuntimeCollection(data=())

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        return RuntimeCollection(data=())

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        return RuntimeCollection(data=())


def _normalize_root(value: PathInput, field_name: str) -> Path:
    raw_value = os.fspath(value)
    if not raw_value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return Path(value)
