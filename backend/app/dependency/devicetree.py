from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.dependency.model import (
    DependencyEvidence,
    DependencyEvidenceKind,
    DependencyKind,
    DependencyReference,
    DependencyResolution,
)
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


class _ProviderResolution(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class _PhandleArraySpec:
    property_name: str
    names_property: str | None
    kind: DependencyKind
    provider_cell_property: str


@dataclass(frozen=True)
class _ResolvedProvider:
    resolution: _ProviderResolution
    provider_dt_path: str | None
    cell_count: int | None
    message: str | None = None


@dataclass(frozen=True)
class _InterruptParent:
    provider_dt_path: str | None
    provider_phandle: int | None
    cell_count: int | None
    resolution: DependencyResolution
    message: str | None = None


_GENERIC_PHANDLE_ARRAYS = (
    _PhandleArraySpec(
        property_name="clocks",
        names_property="clock-names",
        kind=DependencyKind.CLOCK,
        provider_cell_property="#clock-cells",
    ),
    _PhandleArraySpec(
        property_name="resets",
        names_property="reset-names",
        kind=DependencyKind.RESET,
        provider_cell_property="#reset-cells",
    ),
    _PhandleArraySpec(
        property_name="power-domains",
        names_property="power-domain-names",
        kind=DependencyKind.POWER_DOMAIN,
        provider_cell_property="#power-domain-cells",
    ),
    _PhandleArraySpec(
        property_name="dmas",
        names_property="dma-names",
        kind=DependencyKind.DMA,
        provider_cell_property="#dma-cells",
    ),
    _PhandleArraySpec(
        property_name="iommus",
        names_property="iommu-names",
        kind=DependencyKind.IOMMU,
        provider_cell_property="#iommu-cells",
    ),
)
_INTERRUPTS_EXTENDED_SPEC = _PhandleArraySpec(
    property_name="interrupts-extended",
    names_property="interrupt-names",
    kind=DependencyKind.INTERRUPT,
    provider_cell_property="#interrupt-cells",
)


class PhandleResolver:
    def __init__(self, phandles: dict[int, tuple[DeviceTreeNode, ...]]) -> None:
        self._phandles = phandles

    @classmethod
    def from_tree(cls, tree: DeviceTree) -> "PhandleResolver":
        phandles: dict[int, list[DeviceTreeNode]] = {}

        for node in tree.iter_nodes():
            node_phandles: set[int] = set()
            for prop_name in ("phandle", "linux,phandle"):
                phandle = _read_single_cell(node.get_property(prop_name))
                if phandle is not None:
                    node_phandles.add(phandle)

            for phandle in node_phandles:
                phandles.setdefault(phandle, []).append(node)

        return cls(
            {
                phandle: tuple(nodes)
                for phandle, nodes in phandles.items()
            }
        )

    def resolve(self, phandle: int) -> tuple[DeviceTreeNode, ...]:
        return self._phandles.get(phandle, ())


class PhandleArrayInterpreter:
    def __init__(self, resolver: PhandleResolver) -> None:
        self._resolver = resolver

    def interpret(
        self,
        node: DeviceTreeNode,
        spec: _PhandleArraySpec,
    ) -> tuple[DependencyReference, ...]:
        prop = node.get_property(spec.property_name)
        cells = _read_cells(prop)
        if prop is None:
            return ()

        names = _read_names(node.get_property(spec.names_property))
        source_path = _join_dt_path(node.path, spec.property_name)

        if cells is None:
            return (
                _reference(
                    kind=spec.kind,
                    consumer_dt_path=node.path,
                    provider_dt_path=None,
                    provider_phandle=None,
                    entry_index=0,
                    name=_name_at(names, 0),
                    specifier_cells=(),
                    source_property=spec.property_name,
                    resolution=DependencyResolution.UNAVAILABLE,
                    source_path=source_path,
                    message=f"{spec.property_name} is not a valid cell array",
                ),
            )

        return self._interpret_cells(
            node=node,
            cells=cells,
            names=names,
            spec=spec,
            source_path=source_path,
        )

    def _interpret_cells(
        self,
        node: DeviceTreeNode,
        cells: tuple[int, ...],
        names: tuple[str, ...],
        spec: _PhandleArraySpec,
        source_path: str,
    ) -> tuple[DependencyReference, ...]:
        references: list[DependencyReference] = []
        offset = 0
        entry_index = 0

        while offset < len(cells):
            provider_phandle = cells[offset]
            offset += 1
            provider = self._resolve_provider(provider_phandle, spec)

            if provider.resolution != _ProviderResolution.RESOLVED:
                references.append(
                    _reference(
                        kind=spec.kind,
                        consumer_dt_path=node.path,
                        provider_dt_path=provider.provider_dt_path,
                        provider_phandle=provider_phandle,
                        entry_index=entry_index,
                        name=_name_at(names, entry_index),
                        specifier_cells=cells[offset:],
                        source_property=spec.property_name,
                        resolution=_to_dependency_resolution(provider.resolution),
                        source_path=source_path,
                        message=provider.message,
                    )
                )
                break

            cell_count = provider.cell_count
            if cell_count is None:
                references.append(
                    _reference(
                        kind=spec.kind,
                        consumer_dt_path=node.path,
                        provider_dt_path=provider.provider_dt_path,
                        provider_phandle=provider_phandle,
                        entry_index=entry_index,
                        name=_name_at(names, entry_index),
                        specifier_cells=cells[offset:],
                        source_property=spec.property_name,
                        resolution=DependencyResolution.UNAVAILABLE,
                        source_path=source_path,
                        message=(
                            f"Provider is missing valid "
                            f"{spec.provider_cell_property}"
                        ),
                    )
                )
                break

            next_offset = offset + cell_count
            if next_offset > len(cells):
                references.append(
                    _reference(
                        kind=spec.kind,
                        consumer_dt_path=node.path,
                        provider_dt_path=provider.provider_dt_path,
                        provider_phandle=provider_phandle,
                        entry_index=entry_index,
                        name=_name_at(names, entry_index),
                        specifier_cells=cells[offset:],
                        source_property=spec.property_name,
                        resolution=DependencyResolution.UNAVAILABLE,
                        source_path=source_path,
                        message=f"{spec.property_name} ends in a partial entry",
                    )
                )
                break

            references.append(
                _reference(
                    kind=spec.kind,
                    consumer_dt_path=node.path,
                    provider_dt_path=provider.provider_dt_path,
                    provider_phandle=provider_phandle,
                    entry_index=entry_index,
                    name=_name_at(names, entry_index),
                    specifier_cells=cells[offset:next_offset],
                    source_property=spec.property_name,
                    resolution=DependencyResolution.RESOLVED,
                    source_path=source_path,
                )
            )
            offset = next_offset
            entry_index += 1

        return tuple(references)

    def _resolve_provider(
        self,
        provider_phandle: int,
        spec: _PhandleArraySpec,
    ) -> _ResolvedProvider:
        providers = self._resolver.resolve(provider_phandle)
        if not providers:
            return _ResolvedProvider(
                resolution=_ProviderResolution.UNRESOLVED,
                provider_dt_path=None,
                cell_count=None,
                message=f"Provider phandle 0x{provider_phandle:x} was not found",
            )

        if len(providers) > 1:
            return _ResolvedProvider(
                resolution=_ProviderResolution.AMBIGUOUS,
                provider_dt_path=None,
                cell_count=None,
                message=f"Provider phandle 0x{provider_phandle:x} matches multiple nodes",
            )

        provider = providers[0]
        cell_count = _read_single_cell(provider.get_property(spec.provider_cell_property))
        if cell_count is None:
            return _ResolvedProvider(
                resolution=_ProviderResolution.RESOLVED,
                provider_dt_path=provider.path,
                cell_count=None,
            )

        return _ResolvedProvider(
            resolution=_ProviderResolution.RESOLVED,
            provider_dt_path=provider.path,
            cell_count=cell_count,
        )


class DeviceTreeDependencyExtractor:
    def extract(self, tree: DeviceTree) -> tuple[DependencyReference, ...]:
        resolver = PhandleResolver.from_tree(tree)
        interpreter = PhandleArrayInterpreter(resolver)

        references: list[DependencyReference] = []
        for node in tree.iter_nodes():
            for spec in _GENERIC_PHANDLE_ARRAYS:
                references.extend(interpreter.interpret(node, spec))
            if node.get_property("interrupts-extended") is not None:
                references.extend(interpreter.interpret(node, _INTERRUPTS_EXTENDED_SPEC))
            else:
                references.extend(self._extract_interrupts(node, tree, resolver))

        return tuple(references)

    def _extract_interrupts(
        self,
        node: DeviceTreeNode,
        tree: DeviceTree,
        resolver: PhandleResolver,
    ) -> tuple[DependencyReference, ...]:
        prop = node.get_property("interrupts")
        if prop is None:
            return ()

        cells = _read_cells(prop)
        names = _read_names(node.get_property("interrupt-names"))
        source_path = _join_dt_path(node.path, "interrupts")
        if cells is None:
            return (
                _reference(
                    kind=DependencyKind.INTERRUPT,
                    consumer_dt_path=node.path,
                    provider_dt_path=None,
                    provider_phandle=None,
                    entry_index=0,
                    name=_name_at(names, 0),
                    specifier_cells=(),
                    source_property="interrupts",
                    resolution=DependencyResolution.UNAVAILABLE,
                    source_path=source_path,
                    message="interrupts is not a valid cell array",
                ),
            )

        parent = self._find_interrupt_parent(node, tree, resolver)
        if parent.resolution != DependencyResolution.RESOLVED:
            return (
                _reference(
                    kind=DependencyKind.INTERRUPT,
                    consumer_dt_path=node.path,
                    provider_dt_path=parent.provider_dt_path,
                    provider_phandle=parent.provider_phandle,
                    entry_index=0,
                    name=_name_at(names, 0),
                    specifier_cells=cells,
                    source_property="interrupts",
                    resolution=parent.resolution,
                    source_path=source_path,
                    message=parent.message,
                ),
            )

        if parent.cell_count is None or parent.cell_count == 0:
            return (
                _reference(
                    kind=DependencyKind.INTERRUPT,
                    consumer_dt_path=node.path,
                    provider_dt_path=parent.provider_dt_path,
                    provider_phandle=parent.provider_phandle,
                    entry_index=0,
                    name=_name_at(names, 0),
                    specifier_cells=cells,
                    source_property="interrupts",
                    resolution=DependencyResolution.UNAVAILABLE,
                    source_path=source_path,
                    message="Interrupt provider is missing valid #interrupt-cells",
                ),
            )

        return self._split_interrupt_cells(
            node=node,
            cells=cells,
            names=names,
            provider_phandle=parent.provider_phandle,
            provider_dt_path=parent.provider_dt_path,
            cell_count=parent.cell_count,
            source_path=source_path,
        )

    def _split_interrupt_cells(
        self,
        node: DeviceTreeNode,
        cells: tuple[int, ...],
        names: tuple[str, ...],
        provider_phandle: int | None,
        provider_dt_path: str | None,
        cell_count: int,
        source_path: str,
    ) -> tuple[DependencyReference, ...]:
        references: list[DependencyReference] = []
        offset = 0
        entry_index = 0

        while offset < len(cells):
            next_offset = offset + cell_count
            if next_offset > len(cells):
                references.append(
                    _reference(
                        kind=DependencyKind.INTERRUPT,
                        consumer_dt_path=node.path,
                        provider_dt_path=provider_dt_path,
                        provider_phandle=provider_phandle,
                        entry_index=entry_index,
                        name=_name_at(names, entry_index),
                        specifier_cells=cells[offset:],
                        source_property="interrupts",
                        resolution=DependencyResolution.UNAVAILABLE,
                        source_path=source_path,
                        message="interrupts ends in a partial entry",
                    )
                )
                break

            references.append(
                _reference(
                    kind=DependencyKind.INTERRUPT,
                    consumer_dt_path=node.path,
                    provider_dt_path=provider_dt_path,
                    provider_phandle=provider_phandle,
                    entry_index=entry_index,
                    name=_name_at(names, entry_index),
                    specifier_cells=cells[offset:next_offset],
                    source_property="interrupts",
                    resolution=DependencyResolution.RESOLVED,
                    source_path=source_path,
                )
            )
            offset = next_offset
            entry_index += 1

        return tuple(references)

    def _find_interrupt_parent(
        self,
        node: DeviceTreeNode,
        tree: DeviceTree,
        resolver: PhandleResolver,
    ) -> _InterruptParent:
        current: DeviceTreeNode | None = node
        while current is not None:
            prop = current.get_property("interrupt-parent")
            if prop is not None:
                cells = _read_cells(prop)
                if cells is None or len(cells) != 1:
                    return _InterruptParent(
                        provider_dt_path=None,
                        provider_phandle=None,
                        cell_count=None,
                        resolution=DependencyResolution.UNAVAILABLE,
                        message="interrupt-parent is not a single cell",
                    )

                return _resolve_interrupt_provider(cells[0], resolver)

            parent = (
                None
                if current.parent_path is None
                else tree.get_node(current.parent_path)
            )
            if parent is None:
                break

            cell_count = _read_single_cell(parent.get_property("#interrupt-cells"))
            if cell_count is not None:
                return _InterruptParent(
                    provider_dt_path=parent.path,
                    provider_phandle=_read_node_phandle(parent),
                    cell_count=cell_count,
                    resolution=DependencyResolution.RESOLVED,
                )

            current = parent

        return _InterruptParent(
            provider_dt_path=None,
            provider_phandle=None,
            cell_count=None,
            resolution=DependencyResolution.UNAVAILABLE,
            message="interrupt-parent was not found",
        )


def _reference(
    *,
    kind: DependencyKind,
    consumer_dt_path: str,
    provider_dt_path: str | None,
    provider_phandle: int | None,
    entry_index: int,
    name: str | None,
    specifier_cells: tuple[int, ...],
    source_property: str,
    resolution: DependencyResolution,
    source_path: str,
    message: str | None = None,
) -> DependencyReference:
    return DependencyReference(
        kind=kind,
        consumer_dt_path=consumer_dt_path,
        provider_dt_path=provider_dt_path,
        entry_index=entry_index,
        provider_phandle=provider_phandle,
        name=name,
        specifier_cells=specifier_cells,
        source_property=source_property,
        resolution=resolution,
        evidence=(
            DependencyEvidence(
                kind=DependencyEvidenceKind.DECLARED,
                source="devicetree",
                source_path=source_path,
                message=message,
            ),
        ),
    )


def _read_cells(prop: DeviceTreeProperty | None) -> tuple[int, ...] | None:
    if prop is None:
        return None

    if prop.kind == PropertyKind.CELLS and isinstance(prop.value, tuple):
        if all(type(item) is int for item in prop.value):
            return prop.value

    if len(prop.raw_bytes) % 4 != 0:
        return None

    return tuple(
        int.from_bytes(prop.raw_bytes[index : index + 4], byteorder="big")
        for index in range(0, len(prop.raw_bytes), 4)
    )


def _read_single_cell(prop: DeviceTreeProperty | None) -> int | None:
    cells = _read_cells(prop)
    if cells is None or len(cells) != 1:
        return None
    return cells[0]


def _resolve_interrupt_provider(
    provider_phandle: int,
    resolver: PhandleResolver,
) -> _InterruptParent:
    providers = resolver.resolve(provider_phandle)
    if not providers:
        return _InterruptParent(
            provider_dt_path=None,
            provider_phandle=provider_phandle,
            cell_count=None,
            resolution=DependencyResolution.UNRESOLVED,
            message=f"Provider phandle 0x{provider_phandle:x} was not found",
        )

    if len(providers) > 1:
        return _InterruptParent(
            provider_dt_path=None,
            provider_phandle=provider_phandle,
            cell_count=None,
            resolution=DependencyResolution.AMBIGUOUS,
            message=f"Provider phandle 0x{provider_phandle:x} matches multiple nodes",
        )

    provider = providers[0]
    return _InterruptParent(
        provider_dt_path=provider.path,
        provider_phandle=provider_phandle,
        cell_count=_read_single_cell(provider.get_property("#interrupt-cells")),
        resolution=DependencyResolution.RESOLVED,
    )


def _read_node_phandle(node: DeviceTreeNode) -> int | None:
    for prop_name in ("phandle", "linux,phandle"):
        phandle = _read_single_cell(node.get_property(prop_name))
        if phandle is not None:
            return phandle
    return None


def _read_names(prop: DeviceTreeProperty | None) -> tuple[str, ...]:
    if prop is None:
        return ()

    if isinstance(prop.value, str):
        return (prop.value,)
    if isinstance(prop.value, tuple) and all(isinstance(item, str) for item in prop.value):
        return prop.value

    if not prop.raw_bytes.endswith(b"\x00"):
        return ()

    names: list[str] = []
    for chunk in prop.raw_bytes[:-1].split(b"\x00"):
        try:
            names.append(chunk.decode("utf-8"))
        except UnicodeDecodeError:
            return ()
    return tuple(name for name in names if name)


def _name_at(names: tuple[str, ...], index: int) -> str | None:
    if index >= len(names):
        return None
    return names[index]


def _join_dt_path(node_path: str, property_name: str) -> str:
    if node_path == "/":
        return f"/{property_name}"
    return f"{node_path}/{property_name}"


def _to_dependency_resolution(
    resolution: _ProviderResolution,
) -> DependencyResolution:
    if resolution == _ProviderResolution.UNRESOLVED:
        return DependencyResolution.UNRESOLVED
    if resolution == _ProviderResolution.AMBIGUOUS:
        return DependencyResolution.AMBIGUOUS
    return DependencyResolution.UNAVAILABLE
