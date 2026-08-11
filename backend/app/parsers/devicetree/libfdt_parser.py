from __future__ import annotations

import importlib
from pathlib import Path
from typing import Protocol

from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    ParseResult,
)
from app.parsers.devicetree.decoder import PropertyDecoder


class _LibFdtModule(Protocol):
    QUIET_NOTFOUND: tuple[int, ...]

    def Fdt(self, data: bytes) -> object:
        ...


class LibFdtDeviceTreeParser:
    def __init__(
        self,
        decoder: PropertyDecoder | None = None,
        libfdt_module: _LibFdtModule | None = None,
    ) -> None:
        self._decoder = decoder if decoder is not None else PropertyDecoder()
        self._libfdt_module = libfdt_module

    def parse(self, path: str | Path) -> ParseResult:
        dtb_path = Path(path)
        try:
            data = dtb_path.read_bytes()
        except OSError as exc:
            return ParseResult(
                tree=None,
                source=str(dtb_path),
                errors=(f"Failed to read DTB: {exc}",),
            )

        return self.parse_bytes(data, source=str(dtb_path))

    def parse_bytes(self, data: bytes, source: str | None = None) -> ParseResult:
        try:
            libfdt = self._get_libfdt()
            fdt = libfdt.Fdt(data)
            root_offset = fdt.path_offset("/")
            root = self._parse_node(
                fdt=fdt,
                node_offset=root_offset,
                parent_path=None,
                libfdt=libfdt,
            )
        # Parser boundary: convert libfdt/domain parsing failures into ParseResult.
        except Exception as exc:
            return ParseResult(
                tree=None,
                source=source,
                errors=(f"Failed to parse DTB with pylibfdt: {exc}",),
            )

        return ParseResult(tree=DeviceTree(root=root), source=source)

    def _get_libfdt(self) -> _LibFdtModule:
        if self._libfdt_module is not None:
            return self._libfdt_module

        try:
            return importlib.import_module("libfdt")
        except ImportError as exc:
            raise RuntimeError(
                "pylibfdt is required to parse DTB files. Install the libfdt "
                "Python binding before using LibFdtDeviceTreeParser."
            ) from exc

    def _parse_node(
        self,
        fdt: object,
        node_offset: int,
        parent_path: str | None,
        libfdt: _LibFdtModule,
    ) -> DeviceTreeNode:
        full_name = _normalize_full_name(fdt.get_name(node_offset))
        name, unit_address = _split_full_name(full_name)
        path = _join_path(parent_path, full_name)

        return DeviceTreeNode(
            name=name,
            path=path,
            unit_address=unit_address,
            parent_path=parent_path,
            properties=self._read_properties(fdt, node_offset, libfdt),
            children=self._read_children(fdt, node_offset, path, libfdt),
        )

    def _read_properties(
        self,
        fdt: object,
        node_offset: int,
        libfdt: _LibFdtModule,
    ) -> tuple[DeviceTreeProperty, ...]:
        properties: list[tuple[str, bytes]] = []
        quiet_notfound = _quiet_notfound(libfdt)
        prop_offset = fdt.first_property_offset(node_offset, quiet=quiet_notfound)

        while prop_offset >= 0:
            prop = fdt.get_property_by_offset(prop_offset)
            properties.append((prop.name, bytes(prop)))
            prop_offset = fdt.next_property_offset(prop_offset, quiet=quiet_notfound)

        return self._decoder.decode_many(properties)

    def _read_children(
        self,
        fdt: object,
        node_offset: int,
        parent_path: str,
        libfdt: _LibFdtModule,
    ) -> tuple[DeviceTreeNode, ...]:
        children: list[DeviceTreeNode] = []
        quiet_notfound = _quiet_notfound(libfdt)
        child_offset = fdt.first_subnode(node_offset, quiet=quiet_notfound)

        while child_offset >= 0:
            children.append(
                self._parse_node(
                    fdt=fdt,
                    node_offset=child_offset,
                    parent_path=parent_path,
                    libfdt=libfdt,
                )
            )
            child_offset = fdt.next_subnode(child_offset, quiet=quiet_notfound)

        return tuple(children)


def _quiet_notfound(libfdt: _LibFdtModule) -> tuple[int, ...]:
    return getattr(libfdt, "QUIET_NOTFOUND", ())


def _normalize_full_name(full_name: str) -> str:
    return "/" if full_name in ("", "/") else full_name


def _split_full_name(full_name: str) -> tuple[str, str | None]:
    if full_name == "/":
        return "/", None
    if "@" not in full_name:
        return full_name, None

    name, unit_address = full_name.split("@", 1)
    return name, unit_address


def _join_path(parent_path: str | None, full_name: str) -> str:
    if parent_path is None:
        return "/"
    if parent_path == "/":
        return f"/{full_name}"
    return f"{parent_path}/{full_name}"
