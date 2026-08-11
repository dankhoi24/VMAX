from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.model.devicetree import ParseResult
from app.parsers.devicetree import LibFdtDeviceTreeParser


class DeviceTreeFileParser(Protocol):
    def parse(self, path: str | Path) -> ParseResult:
        ...


class DeviceTreeCollector:
    def __init__(self, parser: DeviceTreeFileParser | None = None) -> None:
        self._parser = parser if parser is not None else LibFdtDeviceTreeParser()

    def collect_from_file(self, path: str | Path) -> ParseResult:
        return self._parser.parse(path)
