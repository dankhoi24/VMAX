import unittest

from app.addressing.reg_interpreter import RegInterpreter
from app.model.addressing import AddressCellContext
from app.model.devicetree import DeviceTreeNode, DeviceTreeProperty, PropertyKind


class RegInterpreterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.interpreter = RegInterpreter()

    def test_decodes_two_address_cells_and_one_size_cell(self) -> None:
        node = node_with_reg(0x00000010, 0x82345000, 0x1000)
        cell_context = make_context(address_cells=2, size_cells=1)

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(warnings, ())
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].node_path, "/soc/device@1082345000")
        self.assertEqual(regions[0].index, 0)
        self.assertEqual(regions[0].bus_address, 0x1082345000)
        self.assertEqual(regions[0].size, 0x1000)

    def test_decodes_multiple_reg_tuples_and_preserves_index(self) -> None:
        node = node_with_reg(
            0x1000,
            0x100,
            0x2000,
            0x200,
            0x5000,
            0x80,
        )
        cell_context = make_context(address_cells=1, size_cells=1)

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(warnings, ())
        self.assertEqual(
            [(region.index, region.bus_address, region.size) for region in regions],
            [
                (0, 0x1000, 0x100),
                (1, 0x2000, 0x200),
                (2, 0x5000, 0x80),
            ],
        )

    def test_size_cells_zero_uses_none_size(self) -> None:
        node = node_with_reg(0x1000, 0x2000)
        cell_context = make_context(address_cells=1, size_cells=0)

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(warnings, ())
        self.assertEqual(
            [(region.index, region.bus_address, region.size) for region in regions],
            [(0, 0x1000, None), (1, 0x2000, None)],
        )

    def test_combines_more_than_two_address_cells_without_truncation(self) -> None:
        node = node_with_reg(0x1, 0x23456789, 0xABCDEF01, 0x20)
        cell_context = make_context(address_cells=3, size_cells=1)

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(warnings, ())
        self.assertEqual(regions[0].bus_address, 0x123456789ABCDEF01)
        self.assertEqual(regions[0].size, 0x20)

    def test_combines_multiple_size_cells(self) -> None:
        node = node_with_reg(0x1000, 0x00000001, 0x00000000)
        cell_context = make_context(address_cells=1, size_cells=2)

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(warnings, ())
        self.assertEqual(regions[0].bus_address, 0x1000)
        self.assertEqual(regions[0].size, 0x1_00000000)

    def test_missing_reg_property_returns_no_regions_or_warnings(self) -> None:
        node = DeviceTreeNode(name="device", path="/soc/device", parent_path="/soc")

        regions, warnings = self.interpreter.interpret(
            node,
            make_context(address_cells=1, size_cells=1),
        )

        self.assertEqual(regions, ())
        self.assertEqual(warnings, ())

    def test_missing_reg_property_ignores_unresolved_context(self) -> None:
        node = DeviceTreeNode(name="device", path="/soc/device", parent_path="/soc")

        regions, warnings = self.interpreter.interpret(node, None)

        self.assertEqual(regions, ())
        self.assertEqual(warnings, ())

    def test_unresolved_context_returns_warning_without_regions(self) -> None:
        node = node_with_reg(0x1000, 0x100)

        regions, warnings = self.interpreter.interpret(node, None)

        self.assertEqual(regions, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["ADDRESS_CELL_CONTEXT_UNRESOLVED"],
        )

    def test_context_source_must_match_node_parent(self) -> None:
        node = node_with_reg(0x1000, 0x100)
        cell_context = AddressCellContext(
            address_cells=1,
            size_cells=1,
            source_node_path="/pcie",
        )

        regions, warnings = self.interpreter.interpret(node, cell_context)

        self.assertEqual(regions, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["ADDRESS_CELL_CONTEXT_MISMATCH"],
        )

    def test_malformed_non_cells_reg_returns_warning_without_regions(self) -> None:
        node = DeviceTreeNode(
            name="device",
            path="/soc/device@1000",
            unit_address="1000",
            parent_path="/soc",
            properties=(
                DeviceTreeProperty(
                    name="reg",
                    raw_bytes=b"0x1000\x00",
                    kind=PropertyKind.STRING,
                    value="0x1000",
                ),
            ),
        )

        regions, warnings = self.interpreter.interpret(
            node,
            make_context(address_cells=1, size_cells=1),
        )

        self.assertEqual(regions, ())
        self.assertEqual([warning.code for warning in warnings], ["MALFORMED_REG"])

    def test_malformed_cell_count_returns_warning_without_partial_regions(self) -> None:
        node = node_with_reg(0x1000, 0x100, 0x2000)

        regions, warnings = self.interpreter.interpret(
            node,
            make_context(address_cells=1, size_cells=1),
        )

        self.assertEqual(regions, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MALFORMED_REG_CELL_COUNT"],
        )

    def test_rejects_cell_values_larger_than_u32(self) -> None:
        node = node_with_reg(0x1_0000_0000, 0x100)

        regions, warnings = self.interpreter.interpret(
            node,
            make_context(address_cells=1, size_cells=1),
        )

        self.assertEqual(regions, ())
        self.assertEqual([warning.code for warning in warnings], ["MALFORMED_REG"])

    def test_rejects_zero_width_context(self) -> None:
        node = node_with_reg()

        regions, warnings = self.interpreter.interpret(
            node,
            make_context(address_cells=0, size_cells=0),
        )

        self.assertEqual(regions, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["INVALID_REG_CELL_CONTEXT"],
        )


def make_context(address_cells: int, size_cells: int) -> AddressCellContext:
    return AddressCellContext(
        address_cells=address_cells,
        size_cells=size_cells,
        source_node_path="/soc",
    )


def node_with_reg(*values: int) -> DeviceTreeNode:
    return DeviceTreeNode(
        name="device",
        path="/soc/device@1082345000",
        unit_address="1082345000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(name="reg", kind=PropertyKind.CELLS, value=values),
        ),
    )


if __name__ == "__main__":
    unittest.main()
