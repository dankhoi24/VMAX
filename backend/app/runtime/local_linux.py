from __future__ import annotations

import os
import socket
from pathlib import Path

from app.runtime.model import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeSystemInfo,
    RuntimeWarning,
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
        warnings: list[RuntimeWarning] = []

        uname = _read_uname(warnings)
        hostname = _read_hostname(warnings)
        cmdline = self._read_proc_cmdline(warnings)
        machine = getattr(uname, "machine", None) if uname is not None else None

        return RuntimeCollection(
            data=RuntimeSystemInfo(
                hostname=hostname,
                kernel_name=_uname_attr(uname, "sysname"),
                kernel_release=_uname_attr(uname, "release"),
                kernel_version=_uname_attr(uname, "version"),
                machine=machine,
                architecture=_normalize_architecture(machine),
                cmdline=cmdline,
            ),
            warnings=tuple(warnings),
        )

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

    def _read_proc_cmdline(self, warnings: list[RuntimeWarning]) -> str | None:
        runtime_path = self._proc_runtime_path("cmdline")
        try:
            return self._proc_access_path("cmdline").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            warnings.append(
                RuntimeWarning(
                    code="PROC_CMDLINE_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None


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


def _read_uname(warnings: list[RuntimeWarning]) -> object | None:
    uname = getattr(os, "uname", None)
    if uname is None:
        warnings.append(
            RuntimeWarning(
                code="UNAME_READ_FAILED",
                message="Unable to read uname: os.uname is not available",
            )
        )
        return None

    try:
        return uname()
    except OSError as error:
        warnings.append(
            RuntimeWarning(
                code="UNAME_READ_FAILED",
                message=f"Unable to read uname: {error}",
            )
        )
        return None


def _read_hostname(warnings: list[RuntimeWarning]) -> str | None:
    try:
        return socket.gethostname()
    except OSError as error:
        warnings.append(
            RuntimeWarning(
                code="HOSTNAME_READ_FAILED",
                message=f"Unable to read hostname: {error}",
            )
        )
        return None


def _uname_attr(uname: object | None, name: str) -> str | None:
    return getattr(uname, name, None) if uname is not None else None


def _normalize_architecture(machine: str | None) -> str | None:
    if machine is None:
        return None

    normalized = machine.lower()
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    if normalized in {"x86_64", "amd64"}:
        return "x86_64"
    if normalized == "riscv64":
        return "riscv64"
    return normalized


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)
