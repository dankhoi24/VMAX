from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Protocol


PathInput = str | os.PathLike[str]


class RuntimeTransportError(OSError):
    """Raised when runtime transport IO fails outside normal local errno cases."""


class RuntimeTransportUnavailable(RuntimeTransportError):
    """Raised when a local runtime operation is unavailable on this host."""


class RuntimeTransport(Protocol):
    """Transport boundary for runtime OS/filesystem access."""

    @property
    def sysfs_root(self) -> Path:
        ...

    @property
    def proc_root(self) -> Path:
        ...

    def sysfs_path(self, relative_path: PathInput) -> Path:
        ...

    def proc_path(self, relative_path: PathInput) -> Path:
        ...

    def iterdir(self, path: Path) -> tuple[Path, ...]:
        ...

    def is_dir(self, path: Path) -> bool:
        ...

    def readlink(self, path: Path) -> Path:
        ...

    def resolve(self, path: Path, *, strict: bool = False) -> Path:
        ...

    def read_text(self, path: Path, *, encoding: str) -> str:
        ...

    def uname(self) -> object:
        ...

    def hostname(self) -> str:
        ...


class LocalRuntimeTransport:
    """Runtime transport backed by the local host filesystem and OS calls."""

    def __init__(
        self,
        sysfs_root: PathInput = Path("/sys"),
        proc_root: PathInput = Path("/proc"),
    ) -> None:
        self._sysfs_root = normalize_root(sysfs_root, "sysfs_root")
        self._proc_root = normalize_root(proc_root, "proc_root")

    @property
    def sysfs_root(self) -> Path:
        return self._sysfs_root

    @property
    def proc_root(self) -> Path:
        return self._proc_root

    def sysfs_path(self, relative_path: PathInput) -> Path:
        return self._sysfs_root / normalize_relative_path(
            relative_path,
            "sysfs relative_path",
        )

    def proc_path(self, relative_path: PathInput) -> Path:
        return self._proc_root / normalize_relative_path(
            relative_path,
            "proc relative_path",
        )

    def iterdir(self, path: Path) -> tuple[Path, ...]:
        return tuple(path.iterdir())

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def readlink(self, path: Path) -> Path:
        return path.readlink()

    def resolve(self, path: Path, *, strict: bool = False) -> Path:
        return path.resolve(strict=strict)

    def read_text(self, path: Path, *, encoding: str) -> str:
        return path.read_text(encoding=encoding)

    def uname(self) -> object:
        uname = getattr(os, "uname", None)
        if uname is None:
            raise RuntimeTransportUnavailable("os.uname is not available")
        return uname()

    def hostname(self) -> str:
        return socket.gethostname()


def normalize_root(value: PathInput, field_name: str) -> Path:
    raw_value = os.fspath(value)
    if not raw_value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return Path(value)


def normalize_relative_path(value: PathInput, field_name: str) -> Path:
    raw_value = os.fspath(value)
    if not raw_value.strip():
        raise ValueError(f"{field_name} must not be empty")

    path = Path(raw_value)
    if raw_value.startswith(("/", "\\")) or path.is_absolute():
        raise ValueError(f"{field_name} must be relative")
    if ".." in path.parts:
        raise ValueError(f"{field_name} must not contain '..'")
    return path
