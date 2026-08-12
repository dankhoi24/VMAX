from __future__ import annotations

from app.model.addressing import AddressCellContext, AddressingWarning, RegRegion
from app.model.devicetree import DeviceTreeNode, DeviceTreeProperty, PropertyKind


REG_PROPERTY = "reg"
MAX_CELL_VALUE = 0xFFFFFFFF


class RegInterpreter:
    def interpret(
        self,
        node: DeviceTreeNode,
        context: AddressCellContext | None,
    ) -> tuple[tuple[RegRegion, ...], tuple[AddressingWarning, ...]]:
        prop = node.get_property(REG_PROPERTY)
        if prop is None:
            return (), ()

        if context is None:
            return (), (
                AddressingWarning(
                    code="ADDRESS_CELL_CONTEXT_UNRESOLVED",
                    node_path=node.path,
                    message="Cannot interpret reg without an address cell context",
                ),
            )

        if (
            node.parent_path is not None
            and context.source_node_path != node.parent_path
        ):
            return (), (
                AddressingWarning(
                    code="ADDRESS_CELL_CONTEXT_MISMATCH",
                    node_path=node.path,
                    message=(
                        f"Address cell context comes from "
                        f"{context.source_node_path}, but node parent is "
                        f"{node.parent_path}"
                    ),
                ),
            )

        cells = _reg_cells(prop)
        if cells is None:
            return (), (
                AddressingWarning(
                    code="MALFORMED_REG",
                    node_path=node.path,
                    message="reg must be a cells property containing 32-bit cell values",
                ),
            )

        tuple_width = context.address_cells + context.size_cells
        if tuple_width == 0:
            return (), (
                AddressingWarning(
                    code="INVALID_REG_CELL_CONTEXT",
                    node_path=node.path,
                    message="reg cannot be interpreted when address and size cells are both zero",
                ),
            )

        if len(cells) == 0 or len(cells) % tuple_width != 0:
            return (), (
                AddressingWarning(
                    code="MALFORMED_REG_CELL_COUNT",
                    node_path=node.path,
                    message=(
                        f"reg has {len(cells)} cells, which is not a non-empty "
                        f"multiple of tuple width {tuple_width}"
                    ),
                ),
            )

        regions: list[RegRegion] = []
        for index, offset in enumerate(range(0, len(cells), tuple_width)):
            address_start = offset
            address_end = address_start + context.address_cells
            size_start = address_end
            size_end = size_start + context.size_cells
            bus_address = _combine_cells(cells[address_start:address_end])
            size = (
                _combine_cells(cells[size_start:size_end])
                if context.size_cells > 0
                else None
            )

            regions.append(
                RegRegion(
                    node_path=node.path,
                    index=index,
                    bus_address=bus_address,
                    size=size,
                )
            )

        return tuple(regions), ()


def _reg_cells(prop: DeviceTreeProperty) -> tuple[int, ...] | None:
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
