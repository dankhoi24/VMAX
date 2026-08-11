from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, TypeAlias


PropertyValue: TypeAlias = bool | str | tuple[str, ...] | tuple[int, ...] | None


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
    value: PropertyValue = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DeviceTreeProperty.name must not be empty")
        if not isinstance(self.kind, PropertyKind):
            object.__setattr__(self, "kind", PropertyKind(self.kind))
        object.__setattr__(self, "value", _normalize_property_value(self.value))

    @property
    def raw_hex(self) -> str:
        return self.raw_bytes.hex()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "raw_hex": self.raw_hex,
            "kind": self.kind.value,
            "value": _json_safe_value(self.value),
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

    @property
    def full_name(self) -> str:
        if self.name == "/":
            return "/"
        if self.unit_address is None:
            return self.name
        return f"{self.name}@{self.unit_address}"

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

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "full_name": self.full_name,
            "path": self.path,
            "unit_address": self.unit_address,
            "parent_path": self.parent_path,
            "properties": [prop.to_dict() for prop in self.properties],
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class DeviceTree:
    root: DeviceTreeNode

    def __post_init__(self) -> None:
        if self.root.path != "/":
            raise ValueError("DeviceTree.root must have path '/'")

    def get_node(self, path: str) -> DeviceTreeNode | None:
        return self.root.find_by_path(path)

    def iter_nodes(self) -> Iterator[DeviceTreeNode]:
        return self.root.iter_nodes()

    @property
    def node_count(self) -> int:
        return self.root.node_count

    def to_dict(self) -> dict[str, object]:
        return {
            "node_count": self.node_count,
            "root": self.root.to_dict(),
        }


@dataclass(frozen=True)
class ParseResult:
    tree: DeviceTree | None
    source: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))

    @property
    def ok(self) -> bool:
        return self.tree is not None and not self.errors

    @property
    def node_count(self) -> int:
        return self.tree.node_count if self.tree else 0

    @property
    def root(self) -> DeviceTreeNode | None:
        return self.tree.root if self.tree else None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "source": self.source,
            "node_count": self.node_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "tree": self.tree.to_dict() if self.tree else None,
        }


def _normalize_property_value(value: object) -> PropertyValue:
    if value is None or isinstance(value, bool) or isinstance(value, str):
        return value

    if isinstance(value, list | tuple):
        if all(isinstance(item, str) for item in value):
            return tuple(value)
        if all(type(item) is int for item in value):
            return tuple(value)

    raise TypeError(
        "DeviceTreeProperty.value must be bool, str, tuple/list of str, "
        "tuple/list of int, or None"
    )


def _json_safe_value(value: PropertyValue) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value
