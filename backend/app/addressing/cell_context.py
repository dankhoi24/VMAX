from __future__ import annotations

from app.model.addressing import AddressCellContext, AddressingWarning
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


ADDRESS_CELLS_PROPERTY = "#address-cells"
SIZE_CELLS_PROPERTY = "#size-cells"
DEFAULT_ADDRESS_CELLS = 2
DEFAULT_SIZE_CELLS = 1


class AddressCellContextResolver:
    def resolve(
        self,
        node: DeviceTreeNode,
        tree: DeviceTree,
    ) -> tuple[AddressCellContext, tuple[AddressingWarning, ...]]:
        source_node, parent_warnings = self._get_source_node(node, tree)

        if source_node is None:
            context = AddressCellContext(
                address_cells=DEFAULT_ADDRESS_CELLS,
                size_cells=DEFAULT_SIZE_CELLS,
                source_node_path=node.parent_path or node.path,
                used_default_address_cells=True,
                used_default_size_cells=True,
            )
            return context, parent_warnings

        address_cells, used_default_address_cells, address_warnings = (
            self._read_cell_count(
                source_node=source_node,
                property_name=ADDRESS_CELLS_PROPERTY,
                default_value=DEFAULT_ADDRESS_CELLS,
                default_code="DEFAULT_ADDRESS_CELLS",
                malformed_code="MALFORMED_ADDRESS_CELLS",
            )
        )
        size_cells, used_default_size_cells, size_warnings = self._read_cell_count(
            source_node=source_node,
            property_name=SIZE_CELLS_PROPERTY,
            default_value=DEFAULT_SIZE_CELLS,
            default_code="DEFAULT_SIZE_CELLS",
            malformed_code="MALFORMED_SIZE_CELLS",
        )

        context = AddressCellContext(
            address_cells=address_cells,
            size_cells=size_cells,
            source_node_path=source_node.path,
            used_default_address_cells=used_default_address_cells,
            used_default_size_cells=used_default_size_cells,
        )
        warnings = parent_warnings + address_warnings + size_warnings
        return context, warnings

    def _get_source_node(
        self,
        node: DeviceTreeNode,
        tree: DeviceTree,
    ) -> tuple[DeviceTreeNode | None, tuple[AddressingWarning, ...]]:
        if node.parent_path is None:
            return None, (
                AddressingWarning(
                    code="ROOT_NODE_HAS_NO_PARENT",
                    node_path=node.path,
                    message="Root node has no parent address cell context",
                ),
            )

        parent = tree.get_node(node.parent_path)
        if parent is None:
            return None, (
                AddressingWarning(
                    code="PARENT_NODE_NOT_FOUND",
                    node_path=node.path,
                    message=(
                        f"Parent node {node.parent_path!r} was not found; "
                        "using default address cell context"
                    ),
                ),
            )

        return parent, ()

    def _read_cell_count(
        self,
        *,
        source_node: DeviceTreeNode,
        property_name: str,
        default_value: int,
        default_code: str,
        malformed_code: str,
    ) -> tuple[int, bool, tuple[AddressingWarning, ...]]:
        prop = source_node.get_property(property_name)
        if prop is None:
            return default_value, True, (
                AddressingWarning(
                    code=default_code,
                    node_path=source_node.path,
                    message=(
                        f"{property_name} is missing on {source_node.path}; "
                        f"using default {default_value}"
                    ),
                ),
            )

        value = _single_cell_value(prop)
        if value is None:
            return default_value, True, (
                AddressingWarning(
                    code=malformed_code,
                    node_path=source_node.path,
                    message=(
                        f"{property_name} on {source_node.path} must be a "
                        f"single non-negative cell; using default {default_value}"
                    ),
                ),
            )

        return value, False, ()


def _single_cell_value(prop: DeviceTreeProperty) -> int | None:
    if prop.kind is not PropertyKind.CELLS:
        return None
    if not isinstance(prop.value, tuple) or len(prop.value) != 1:
        return None

    value = prop.value[0]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None

    return value
