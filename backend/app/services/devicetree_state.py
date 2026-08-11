from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.collectors.devicetree import DeviceTreeCollector
from app.model.devicetree import DeviceTree, ParseResult


class DeviceTreeSourceCollector(Protocol):
    def collect_from_file(self, path: str | Path) -> ParseResult:
        ...


class DeviceTreeState:
    def __init__(
        self,
        current_path: str | Path | None = None,
        collector: DeviceTreeSourceCollector | None = None,
    ) -> None:
        self._current_path = Path(current_path) if current_path is not None else None
        self._collector = (
            collector
            if collector is not None
            else DeviceTreeCollector()
        )

    @classmethod
    def from_environment(cls) -> "DeviceTreeState":
        path = os.environ.get("VMAX_DTB_PATH")
        return cls(current_path=path if path else None)

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    def set_current_file(self, path: str | Path) -> None:
        self._current_path = Path(path)

    def collect(self) -> ParseResult:
        if self._current_path is None:
            return ParseResult(
                tree=None,
                errors=("No current DTB source configured",),
            )

        return self._collector.collect_from_file(self._current_path)

    def metadata(self) -> dict[str, object]:
        result = self.collect()
        return {
            "filename": self._filename(),
            "file_size": self._file_size(),
            "node_count": result.node_count,
            "property_count": _count_properties(result.tree),
            "warnings": list(result.warnings),
            "errors": list(result.errors),
        }

    def _filename(self) -> str | None:
        return self._current_path.name if self._current_path is not None else None

    def _file_size(self) -> int | None:
        if self._current_path is None:
            return None
        try:
            return self._current_path.stat().st_size
        except OSError:
            return None


def _count_properties(tree: DeviceTree | None) -> int:
    if tree is None:
        return 0
    return sum(len(node.properties) for node in tree.iter_nodes())
