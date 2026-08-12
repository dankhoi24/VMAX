import unittest

from app.addressing.cell_context import AddressCellContextResolver
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


class AddressCellContextResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = AddressCellContextResolver()

    def test_resolves_explicit_parent_context(self) -> None:
        tree, uart = make_tree(
            parent_properties=(
                cells("#address-cells", 2),
                cells("#size-cells", 1),
            )
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertEqual(context.source_node_path, "/soc")
        self.assertFalse(context.used_default_address_cells)
        self.assertFalse(context.used_default_size_cells)
        self.assertEqual(warnings, ())

    def test_resolves_explicit_one_cell_parent_context(self) -> None:
        tree, uart = make_tree(
            parent_properties=(
                cells("#address-cells", 1),
                cells("#size-cells", 1),
            )
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 1)
        self.assertEqual(context.size_cells, 1)
        self.assertEqual(warnings, ())

    def test_accepts_zero_size_cells_without_warning(self) -> None:
        tree, uart = make_tree(
            parent_properties=(
                cells("#address-cells", 2),
                cells("#size-cells", 0),
            )
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 0)
        self.assertFalse(context.used_default_size_cells)
        self.assertEqual(warnings, ())

    def test_missing_parent_properties_use_defaults_with_warnings(self) -> None:
        tree, uart = make_tree(parent_properties=())

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertTrue(context.used_default_address_cells)
        self.assertTrue(context.used_default_size_cells)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["DEFAULT_ADDRESS_CELLS", "DEFAULT_SIZE_CELLS"],
        )
        self.assertEqual([warning.node_path for warning in warnings], ["/soc", "/soc"])

    def test_only_missing_address_cells_uses_default_address_cells(self) -> None:
        tree, uart = make_tree(parent_properties=(cells("#size-cells", 0),))

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 0)
        self.assertTrue(context.used_default_address_cells)
        self.assertFalse(context.used_default_size_cells)
        self.assertEqual([warning.code for warning in warnings], ["DEFAULT_ADDRESS_CELLS"])

    def test_only_missing_size_cells_uses_default_size_cells(self) -> None:
        tree, uart = make_tree(parent_properties=(cells("#address-cells", 1),))

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.address_cells, 1)
        self.assertEqual(context.size_cells, 1)
        self.assertFalse(context.used_default_address_cells)
        self.assertTrue(context.used_default_size_cells)
        self.assertEqual([warning.code for warning in warnings], ["DEFAULT_SIZE_CELLS"])

    def test_context_does_not_inherit_from_grandparent(self) -> None:
        uart = DeviceTreeNode(
            name="uart",
            path="/bus/uart@1000",
            unit_address="1000",
            parent_path="/bus",
        )
        bus = DeviceTreeNode(name="bus", path="/bus", parent_path="/", children=(uart,))
        root = DeviceTreeNode(
            name="/",
            path="/",
            properties=(cells("#address-cells", 1), cells("#size-cells", 0)),
            children=(bus,),
        )
        tree = DeviceTree(root=root)

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertEqual(context.source_node_path, "/bus")
        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertTrue(context.used_default_address_cells)
        self.assertTrue(context.used_default_size_cells)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["DEFAULT_ADDRESS_CELLS", "DEFAULT_SIZE_CELLS"],
        )

    def test_child_of_root_uses_root_as_context_source(self) -> None:
        soc = DeviceTreeNode(name="soc", path="/soc", parent_path="/")
        root = DeviceTreeNode(
            name="/",
            path="/",
            properties=(cells("#address-cells", 1), cells("#size-cells", 0)),
            children=(soc,),
        )
        tree = DeviceTree(root=root)

        context, warnings = self.resolver.resolve(soc, tree)

        self.assertEqual(context.source_node_path, "/")
        self.assertEqual(context.address_cells, 1)
        self.assertEqual(context.size_cells, 0)
        self.assertEqual(warnings, ())

    def test_root_node_uses_defaults_with_no_parent_warning(self) -> None:
        root = DeviceTreeNode(name="/", path="/")
        tree = DeviceTree(root=root)

        context, warnings = self.resolver.resolve(root, tree)

        self.assertEqual(context.source_node_path, "/")
        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertTrue(context.used_default_address_cells)
        self.assertTrue(context.used_default_size_cells)
        self.assertEqual([warning.code for warning in warnings], ["ROOT_NODE_HAS_NO_PARENT"])

    def test_missing_parent_node_uses_defaults_with_warning(self) -> None:
        orphan = DeviceTreeNode(
            name="uart",
            path="/soc/uart@1000",
            unit_address="1000",
            parent_path="/soc",
        )
        tree = DeviceTree(root=DeviceTreeNode(name="/", path="/"))

        context, warnings = self.resolver.resolve(orphan, tree)

        self.assertEqual(context.source_node_path, "/soc")
        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertTrue(context.used_default_address_cells)
        self.assertTrue(context.used_default_size_cells)
        self.assertEqual([warning.code for warning in warnings], ["PARENT_NODE_NOT_FOUND"])

    def test_malformed_non_cell_property_leaves_context_unresolved(self) -> None:
        malformed_address_cells = DeviceTreeProperty(
            name="#address-cells",
            raw_bytes=b"2\x00",
            kind=PropertyKind.STRING,
            value="2",
        )
        tree, uart = make_tree(
            parent_properties=(malformed_address_cells, cells("#size-cells", 1))
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertIsNone(context)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MALFORMED_ADDRESS_CELLS"],
        )

    def test_malformed_multiple_cell_value_leaves_context_unresolved(self) -> None:
        tree, uart = make_tree(
            parent_properties=(
                cells("#address-cells", 1),
                cells("#size-cells", 1, 2),
            )
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertIsNone(context)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MALFORMED_SIZE_CELLS"],
        )

    def test_malformed_property_does_not_use_missing_default_semantics(self) -> None:
        malformed_address_cells = DeviceTreeProperty(
            name="#address-cells",
            raw_bytes=b"\x01\x02",
            kind=PropertyKind.UNKNOWN,
            value=None,
        )
        tree, uart = make_tree(
            parent_properties=(
                malformed_address_cells,
                cells("#size-cells", 1),
            )
        )

        context, warnings = self.resolver.resolve(uart, tree)

        self.assertIsNone(context)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].code, "MALFORMED_ADDRESS_CELLS")


def cells(name: str, *values: int) -> DeviceTreeProperty:
    return DeviceTreeProperty(name=name, kind=PropertyKind.CELLS, value=values)


def make_tree(
    parent_properties: tuple[DeviceTreeProperty, ...],
) -> tuple[DeviceTree, DeviceTreeNode]:
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=parent_properties,
        children=(uart,),
    )
    root = DeviceTreeNode(name="/", path="/", children=(soc,))
    return DeviceTree(root=root), uart


if __name__ == "__main__":
    unittest.main()
