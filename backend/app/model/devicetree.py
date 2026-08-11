from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator


class PropertyKind(str, Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    STRING_LIST = "string_list"
    CELLS = "cells"
    BYTES = "bytes"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DeviceTreeProperty:
    name: str
    raw_bytes: bytes = b""
    kind: PropertyKind = PropertyKind.UNKNOWN
    value: Any = None
    display_value: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DeviceTreeProperty.name must not be empty")
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", PropertyKind(self.kind))

    @property
    def raw_hex(self) -> str:
        return self.raw_bytes.hex()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "raw_hex": self.raw_hex,
            "kind": self.kind.value,
            "value": self.value,
            "display_value": self.display_value,
        }


@dataclass(frozen=True)
class DeviceTreeNode:
    name: str
    path: str
    unit_address: str | None = None
    parent_path: str | None = None
    properties: tuple[DeviceTreeProperty, ...] = field(default_factory=tuple)
    children: tuple["DeviceTreeNode", ...] = field(default_factory=tuple)
    id: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DeviceTreeNode.name must not be empty")
        if not self.path.startswith("/"):
            raise ValueError("DeviceTreeNode.path must be absolute")
        object.__setattr__(self, "id", self.id or self.path)
        object.__setattr__(self, "properties", tuple(self.properties))
        object.__setattr__(self, "children", tuple(self.children))

    def get_property(self, name: str) -> DeviceTreeProperty | None:
        for prop in self.properties:
            if prop.name == name:
                return prop
        return None

    def iter_nodes(self) -> Iterator["DeviceTreeNode"]:
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def find_by_path(self, path: str) -> "DeviceTreeNode | None":
        for node in self.iter_nodes():
            if node.path == path:
                return node
        return None

    @property
    def node_count(self) -> int:
        return sum(1 for _ in self.iter_nodes())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "unit_address": self.unit_address,
            "parent_path": self.parent_path,
            "properties": [prop.to_dict() for prop in self.properties],
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class ParseResult:
    root: DeviceTreeNode | None
    source: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))

    @property
    def ok(self) -> bool:
        return self.root is not None and not self.errors

    @property
    def node_count(self) -> int:
        return self.root.node_count if self.root else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source": self.source,
            "node_count": self.node_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "root": self.root.to_dict() if self.root else None,
        }
