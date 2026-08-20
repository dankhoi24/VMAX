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
    """Runtime provider backed by local filesystem roots.

    sysfs_root and proc_root are access paths used to read files. Domain model
    paths produced by this provider should stay canonical target paths under
    /sys and /proc, even when tests read from fixture roots.
    """

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

    def _sysfs_access_path(self, relative_path: PathInput) -> Path:
        return self._sysfs_root / _normalize_relative_path(
            relative_path,
            "sysfs relative_path",
        )

    def _proc_access_path(self, relative_path: PathInput) -> Path:
        return self._proc_root / _normalize_relative_path(
            relative_path,
            "proc relative_path",
        )

    def _sysfs_runtime_path(self, relative_path: PathInput) -> str:
        return _runtime_path("/sys", relative_path, "sysfs relative_path")

    def _proc_runtime_path(self, relative_path: PathInput) -> str:
        return _runtime_path("/proc", relative_path, "proc relative_path")


def _normalize_root(value: PathInput, field_name: str) -> Path:
    raw_value = os.fspath(value)
    if not raw_value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return Path(value)


def _normalize_relative_path(value: PathInput, field_name: str) -> Path:
    raw_value = os.fspath(value)
    if not raw_value.strip():
        raise ValueError(f"{field_name} must not be empty")

    path = Path(raw_value)
    if raw_value.startswith(("/", "\\")) or path.is_absolute():
        raise ValueError(f"{field_name} must be relative")
    return path


def _runtime_path(root: str, relative_path: PathInput, field_name: str) -> str:
    path = _normalize_relative_path(relative_path, field_name)
    return f"{root}/{path.as_posix()}"
