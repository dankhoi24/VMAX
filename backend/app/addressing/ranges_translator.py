from __future__ import annotations

from app.addressing.cell_context import AddressCellContextResolver
from app.model.addressing import (
    AddressCellContext,
    AddressingWarning,
    RangeMapping,
    RegRegion,
    TranslatedAddressRange,
    TranslationStep,
)
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


RANGES_PROPERTY = "ranges"
MAX_CELL_VALUE = 0xFFFFFFFF
MAX_SIMPLE_NUMERIC_ADDRESS_CELLS = 2


class RangesInterpreter:
    def interpret(
        self,
        bus_node: DeviceTreeNode,
        child_context: AddressCellContext | None,
        parent_context: AddressCellContext | None,
    ) -> tuple[tuple[RangeMapping, ...] | None, tuple[AddressingWarning, ...]]:
        prop = bus_node.get_property(RANGES_PROPERTY)
        if prop is None:
            return None, ()

        cells = _range_cells(prop)
        if cells is None:
            return (), (
                AddressingWarning(
                    code="MALFORMED_RANGES",
                    node_path=bus_node.path,
                    message="ranges must be a cells property containing 32-bit cell values",
                ),
            )

        if child_context is None or parent_context is None:
            return (), (
                AddressingWarning(
                    code="RANGES_CONTEXT_UNRESOLVED",
                    node_path=bus_node.path,
                    message="Cannot interpret ranges without child and parent cell contexts",
                ),
            )

        provenance_warning = _context_provenance_warning(
            bus_node,
            child_context,
            parent_context,
        )
        if provenance_warning is not None:
            return (), (provenance_warning,)

        unsupported_warning = _unsupported_bus_address_warning(
            bus_node,
            child_context,
            parent_context,
        )
        if unsupported_warning is not None:
            return (), (unsupported_warning,)

        if len(cells) == 0:
            return (), ()

        if child_context.size_cells == 0:
            return (), (
                AddressingWarning(
                    code="UNSUPPORTED_RANGES_WITHOUT_SIZE",
                    node_path=bus_node.path,
                    message="Non-empty ranges cannot be interpreted when #size-cells is zero",
                ),
            )

        tuple_width = (
            child_context.address_cells
            + parent_context.address_cells
            + child_context.size_cells
        )
        if tuple_width == 0 or len(cells) % tuple_width != 0:
            return (), (
                AddressingWarning(
                    code="MALFORMED_RANGES_CELL_COUNT",
                    node_path=bus_node.path,
                    message=(
                        f"ranges has {len(cells)} cells, which is not a "
                        f"multiple of tuple width {tuple_width}"
                    ),
                ),
            )

        mappings: list[RangeMapping] = []
        for index, offset in enumerate(range(0, len(cells), tuple_width)):
            child_start = offset
            child_end = child_start + child_context.address_cells
            parent_start = child_end
            parent_end = parent_start + parent_context.address_cells
            size_start = parent_end
            size_end = size_start + child_context.size_cells

            mappings.append(
                RangeMapping(
                    node_path=bus_node.path,
                    index=index,
                    child_address=_combine_cells(cells[child_start:child_end]),
                    parent_address=_combine_cells(cells[parent_start:parent_end]),
                    size=_combine_cells(cells[size_start:size_end]),
                )
            )

        return tuple(mappings), ()


class RangesTranslator:
    def __init__(
        self,
        *,
        context_resolver: AddressCellContextResolver | None = None,
        ranges_interpreter: RangesInterpreter | None = None,
    ) -> None:
        self._context_resolver = context_resolver or AddressCellContextResolver()
        self._ranges_interpreter = ranges_interpreter or RangesInterpreter()

    def translate(
        self,
        region: RegRegion,
        node: DeviceTreeNode,
        tree: DeviceTree,
    ) -> TranslatedAddressRange:
        if region.node_path != node.path:
            warning = AddressingWarning(
                code="REG_REGION_NODE_MISMATCH",
                node_path=node.path,
                message=(
                    f"RegRegion belongs to {region.node_path}, but node is {node.path}"
                ),
            )
            return _untranslated(region, (warning,))

        if node.parent_path is None:
            warning = AddressingWarning(
                code="NODE_HAS_NO_PARENT_BUS",
                node_path=node.path,
                message="Cannot translate a reg region for a node without a parent bus",
            )
            return _untranslated(region, (warning,))

        current_node = node
        current_bus_path = node.parent_path
        current_address = region.bus_address
        steps: list[TranslationStep] = []
        warnings: list[AddressingWarning] = []

        while current_bus_path != "/":
            bus_node = tree.get_node(current_bus_path)
            if bus_node is None:
                warnings.append(
                    AddressingWarning(
                        code="BUS_NODE_NOT_FOUND",
                        node_path=current_node.path,
                        message=(
                            f"Bus node {current_bus_path!r} was not found while "
                            "translating reg address"
                        ),
                    )
                )
                return _untranslated(region, tuple(warnings), tuple(steps))

            child_context, child_warnings = self._context_resolver.resolve(
                current_node,
                tree,
            )
            parent_context, parent_warnings = self._context_resolver.resolve(
                bus_node,
                tree,
            )
            warnings.extend(child_warnings)
            warnings.extend(parent_warnings)

            mappings, mapping_warnings = self._ranges_interpreter.interpret(
                bus_node,
                child_context,
                parent_context,
            )
            warnings.extend(mapping_warnings)

            if mapping_warnings:
                return _untranslated(region, tuple(warnings), tuple(steps))

            if mappings is None:
                warnings.append(
                    AddressingWarning(
                        code="MISSING_RANGES",
                        node_path=bus_node.path,
                        message=(
                            f"Bus node {bus_node.path} has no ranges property; "
                            "address translation is unresolved"
                        ),
                    )
                )
                return _untranslated(region, tuple(warnings), tuple(steps))

            if len(mappings) == 0:
                output_address = current_address
                mapping_index = None
            else:
                mapping = _find_mapping(mappings, current_address, region.size)
                if mapping is None:
                    warnings.append(
                        AddressingWarning(
                        code="RANGE_MAPPING_NOT_FOUND",
                        node_path=bus_node.path,
                        message=(
                                f"No ranges mapping on {bus_node.path} covers "
                                f"region start=0x{current_address:x} "
                                f"size={_format_optional_hex(region.size)}"
                            ),
                        )
                    )
                    return _untranslated(region, tuple(warnings), tuple(steps))

                output_address = (
                    mapping.parent_address + current_address - mapping.child_address
                )
                mapping_index = mapping.index

            steps.append(
                TranslationStep(
                    bus_node_path=bus_node.path,
                    input_address=current_address,
                    output_address=output_address,
                    mapping_index=mapping_index,
                )
            )
            current_address = output_address
            current_node = bus_node
            current_bus_path = bus_node.parent_path

            if current_bus_path is None:
                warning = AddressingWarning(
                    code="BUS_NODE_HAS_NO_PARENT",
                    node_path=current_node.path,
                    message="Translation stopped before reaching the root bus",
                )
                warnings.append(warning)
                return _untranslated(region, tuple(warnings), tuple(steps))

        return TranslatedAddressRange(
            node_path=region.node_path,
            bus_address=region.bus_address,
            cpu_address=current_address,
            size=region.size,
            translation_path=tuple(steps),
            warnings=tuple(warnings),
        )


def _range_cells(prop: DeviceTreeProperty) -> tuple[int, ...] | None:
    if prop.kind is not PropertyKind.CELLS:
        return None
    if not isinstance(prop.value, tuple):
        return None

    for value in prop.value:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            or value > MAX_CELL_VALUE
        ):
            return None

    return prop.value


def _combine_cells(cells: tuple[int, ...]) -> int:
    value = 0
    for cell in cells:
        value = (value << 32) | cell
    return value


def _context_provenance_warning(
    bus_node: DeviceTreeNode,
    child_context: AddressCellContext,
    parent_context: AddressCellContext,
) -> AddressingWarning | None:
    if child_context.source_node_path != bus_node.path:
        return AddressingWarning(
            code="RANGES_CHILD_CONTEXT_MISMATCH",
            node_path=bus_node.path,
            message=(
                f"Ranges child context comes from "
                f"{child_context.source_node_path}, but bus node is {bus_node.path}"
            ),
        )

    if (
        bus_node.parent_path is not None
        and parent_context.source_node_path != bus_node.parent_path
    ):
        return AddressingWarning(
            code="RANGES_PARENT_CONTEXT_MISMATCH",
            node_path=bus_node.path,
            message=(
                f"Ranges parent context comes from "
                f"{parent_context.source_node_path}, but bus parent is "
                f"{bus_node.parent_path}"
            ),
        )

    return None


def _unsupported_bus_address_warning(
    bus_node: DeviceTreeNode,
    child_context: AddressCellContext,
    parent_context: AddressCellContext,
) -> AddressingWarning | None:
    if (
        child_context.address_cells <= MAX_SIMPLE_NUMERIC_ADDRESS_CELLS
        and parent_context.address_cells <= MAX_SIMPLE_NUMERIC_ADDRESS_CELLS
    ):
        return None

    return AddressingWarning(
        code="UNSUPPORTED_BUS_ADDRESS_FORMAT",
        node_path=bus_node.path,
        message=(
            f"Bus node {bus_node.path} uses child={child_context.address_cells}, "
            f"parent={parent_context.address_cells} address cells; generic "
            "ranges translation only supports simple numeric address formats "
            "up to 2 cells"
        ),
    )


def _find_mapping(
    mappings: tuple[RangeMapping, ...],
    address: int,
    size: int | None,
) -> RangeMapping | None:
    for mapping in mappings:
        if _mapping_contains(mapping, address, size):
            return mapping
    return None


def _mapping_contains(mapping: RangeMapping, address: int, size: int | None) -> bool:
    if mapping.size == 0 or address < mapping.child_address:
        return False

    mapping_limit = mapping.child_address + mapping.size
    if size is None or size == 0:
        return address < mapping_limit

    return address + size <= mapping_limit


def _format_optional_hex(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"0x{value:x}"


def _untranslated(
    region: RegRegion,
    warnings: tuple[AddressingWarning, ...],
    steps: tuple[TranslationStep, ...] = (),
) -> TranslatedAddressRange:
    return TranslatedAddressRange(
        node_path=region.node_path,
        bus_address=region.bus_address,
        cpu_address=None,
        size=region.size,
        translation_path=steps,
        warnings=warnings,
    )
