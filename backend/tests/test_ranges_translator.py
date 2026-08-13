import unittest

from app.addressing.ranges_translator import RangesInterpreter, RangesTranslator
from app.model.addressing import AddressCellContext, RegRegion
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


class RangesInterpreterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.interpreter = RangesInterpreter()

    def test_decodes_ranges_with_40_bit_parent_address(self) -> None:
        bus = bus_node(ranges(0x0, 0x10, 0x7D000000, 0x100000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=2, size_cells=1),
        )

        self.assertEqual(warnings, ())
        self.assertIsNotNone(mappings)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0].node_path, "/soc")
        self.assertEqual(mappings[0].index, 0)
        self.assertEqual(mappings[0].child_address, 0x0)
        self.assertEqual(mappings[0].parent_address, 0x107D000000)
        self.assertEqual(mappings[0].size, 0x100000)

    def test_decodes_multiple_ranges(self) -> None:
        bus = bus_node(
            ranges(
                0x0000,
                0x80000000,
                0x1000,
                0x2000,
                0x90000000,
                0x2000,
            )
        )

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(warnings, ())
        self.assertEqual(
            [
                (mapping.index, mapping.child_address, mapping.parent_address, mapping.size)
                for mapping in mappings
            ],
            [
                (0, 0x0000, 0x80000000, 0x1000),
                (1, 0x2000, 0x90000000, 0x2000),
            ],
        )

    def test_missing_ranges_returns_none(self) -> None:
        mappings, warnings = self.interpreter.interpret(
            bus_node(),
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertIsNone(mappings)
        self.assertEqual(warnings, ())

    def test_empty_ranges_returns_identity_marker(self) -> None:
        mappings, warnings = self.interpreter.interpret(
            bus_node(ranges()),
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(warnings, ())

    def test_empty_ranges_still_validates_context_provenance(self) -> None:
        mappings, warnings = self.interpreter.interpret(
            bus_node(ranges()),
            child_context=cell_context("/pcie", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["RANGES_CHILD_CONTEXT_MISMATCH"],
        )

    def test_malformed_ranges_property_returns_warning(self) -> None:
        bus = bus_node(
            DeviceTreeProperty(
                name="ranges",
                raw_bytes=b"bad\x00",
                kind=PropertyKind.STRING,
                value="bad",
            )
        )

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual([warning.code for warning in warnings], ["MALFORMED_RANGES"])

    def test_malformed_ranges_cell_count_returns_no_partial_mappings(self) -> None:
        bus = bus_node(ranges(0x0, 0x80000000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MALFORMED_RANGES_CELL_COUNT"],
        )

    def test_non_empty_ranges_need_resolved_contexts(self) -> None:
        bus = bus_node(ranges(0x0, 0x80000000, 0x1000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=None,
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["RANGES_CONTEXT_UNRESOLVED"],
        )

    def test_child_context_must_come_from_bus_node(self) -> None:
        bus = bus_node(ranges(0x0, 0x80000000, 0x1000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/pcie", address_cells=1, size_cells=1),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["RANGES_CHILD_CONTEXT_MISMATCH"],
        )

    def test_parent_context_must_come_from_bus_parent(self) -> None:
        bus = bus_node(ranges(0x0, 0x80000000, 0x1000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=1),
            parent_context=cell_context("/pcie", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["RANGES_PARENT_CONTEXT_MISMATCH"],
        )

    def test_complex_bus_address_format_is_unsupported(self) -> None:
        bus = bus_node(
            ranges(
                0x02000000,
                0x00000000,
                0x40000000,
                0x00000000,
                0x40000000,
                0x00001000,
            )
        )

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=3, size_cells=1),
            parent_context=cell_context("/", address_cells=2, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["UNSUPPORTED_BUS_ADDRESS_FORMAT"],
        )

    def test_non_empty_ranges_with_zero_size_cells_are_unsupported(self) -> None:
        bus = bus_node(ranges(0x0, 0x80000000))

        mappings, warnings = self.interpreter.interpret(
            bus,
            child_context=cell_context("/soc", address_cells=1, size_cells=0),
            parent_context=cell_context("/", address_cells=1, size_cells=1),
        )

        self.assertEqual(mappings, ())
        self.assertEqual(
            [warning.code for warning in warnings],
            ["UNSUPPORTED_RANGES_WITHOUT_SIZE"],
        )


class RangesTranslatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.translator = RangesTranslator()

    def test_translates_reg_region_through_single_bus_range(self) -> None:
        tree, device = make_single_bus_tree(ranges(0x0, 0x10, 0x7D000000, 0x100000))
        region = reg_region(device.path, bus_address=0x1000, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertEqual(translated.cpu_address, 0x107D001000)
        self.assertEqual(translated.end, 0x107D0010FF)
        self.assertEqual(translated.warnings, ())
        self.assertEqual(len(translated.translation_path), 1)
        self.assertEqual(translated.translation_path[0].bus_node_path, "/soc")
        self.assertEqual(translated.translation_path[0].input_address, 0x1000)
        self.assertEqual(translated.translation_path[0].output_address, 0x107D001000)
        self.assertEqual(translated.translation_path[0].mapping_index, 0)

    def test_translator_selects_second_matching_mapping(self) -> None:
        tree, device = make_single_bus_tree(
            ranges(
                0x0000,
                0x0,
                0x80000000,
                0x1000,
                0x2000,
                0x0,
                0x90000000,
                0x2000,
            )
        )
        region = reg_region(device.path, bus_address=0x2100, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertEqual(translated.cpu_address, 0x90000100)
        self.assertEqual(translated.warnings, ())
        self.assertEqual(translated.translation_path[0].mapping_index, 1)

    def test_empty_ranges_translates_as_identity(self) -> None:
        tree, device = make_single_bus_tree(ranges())
        region = reg_region(device.path, bus_address=0x1000, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertEqual(translated.cpu_address, 0x1000)
        self.assertEqual(translated.warnings, ())
        self.assertEqual(translated.translation_path[0].mapping_index, None)
        self.assertEqual(translated.translation_path[0].input_address, 0x1000)
        self.assertEqual(translated.translation_path[0].output_address, 0x1000)

    def test_missing_ranges_does_not_translate_as_identity(self) -> None:
        tree, device = make_single_bus_tree()
        region = reg_region(device.path, bus_address=0x1000, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertIsNone(translated.cpu_address)
        self.assertEqual(translated.translation_path, ())
        self.assertEqual([warning.code for warning in translated.warnings], ["MISSING_RANGES"])

    def test_nested_bus_translation_preserves_steps(self) -> None:
        device = DeviceTreeNode(
            name="device",
            path="/busb/busa/device@100",
            unit_address="100",
            parent_path="/busb/busa",
        )
        busa = DeviceTreeNode(
            name="busa",
            path="/busb/busa",
            parent_path="/busb",
            properties=(
                cells("#address-cells", 1),
                cells("#size-cells", 1),
                ranges(0x0, 0x20000, 0x10000),
            ),
            children=(device,),
        )
        busb = DeviceTreeNode(
            name="busb",
            path="/busb",
            parent_path="/",
            properties=(
                cells("#address-cells", 1),
                cells("#size-cells", 1),
                ranges(0x20000, 0x10, 0x7D000000, 0x100000),
            ),
            children=(busa,),
        )
        root = DeviceTreeNode(
            name="/",
            path="/",
            properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
            children=(busb,),
        )
        tree = DeviceTree(root=root)
        region = reg_region(device.path, bus_address=0x100, size=0x10)

        translated = self.translator.translate(region, device, tree)

        self.assertEqual(translated.cpu_address, 0x107D000100)
        self.assertEqual(translated.warnings, ())
        self.assertEqual(
            [
                (step.bus_node_path, step.input_address, step.output_address)
                for step in translated.translation_path
            ],
            [
                ("/busb/busa", 0x100, 0x20100),
                ("/busb", 0x20100, 0x107D000100),
            ],
        )

    def test_region_outside_ranges_returns_warning(self) -> None:
        tree, device = make_single_bus_tree(ranges(0x0, 0x0, 0x80000000, 0x100))
        region = reg_region(device.path, bus_address=0x200, size=0x10)

        translated = self.translator.translate(region, device, tree)

        self.assertIsNone(translated.cpu_address)
        self.assertEqual(
            [warning.code for warning in translated.warnings],
            ["RANGE_MAPPING_NOT_FOUND"],
        )

    def test_region_must_fit_entirely_in_range_mapping(self) -> None:
        tree, device = make_single_bus_tree(ranges(0x0, 0x0, 0x80000000, 0x100))
        region = reg_region(device.path, bus_address=0x80, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertIsNone(translated.cpu_address)
        self.assertEqual(
            [warning.code for warning in translated.warnings],
            ["RANGE_MAPPING_NOT_FOUND"],
        )

    def test_child_of_root_is_already_cpu_visible(self) -> None:
        device = DeviceTreeNode(name="device", path="/device@1000", parent_path="/")
        tree = DeviceTree(root=DeviceTreeNode(name="/", path="/", children=(device,)))
        region = reg_region(device.path, bus_address=0x1000, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertEqual(translated.cpu_address, 0x1000)
        self.assertEqual(translated.translation_path, ())
        self.assertEqual(translated.warnings, ())

    def test_reg_region_must_belong_to_node(self) -> None:
        tree, device = make_single_bus_tree(ranges())
        region = reg_region("/other/device@1000", bus_address=0x1000, size=0x100)

        translated = self.translator.translate(region, device, tree)

        self.assertIsNone(translated.cpu_address)
        self.assertEqual(
            [warning.code for warning in translated.warnings],
            ["REG_REGION_NODE_MISMATCH"],
        )


def make_single_bus_tree(
    ranges_property: DeviceTreeProperty | None = None,
) -> tuple[DeviceTree, DeviceTreeNode]:
    device = DeviceTreeNode(
        name="device",
        path="/soc/device@1000",
        unit_address="1000",
        parent_path="/soc",
    )
    soc_properties = [cells("#address-cells", 1), cells("#size-cells", 1)]
    if ranges_property is not None:
        soc_properties.append(ranges_property)
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=tuple(soc_properties),
        children=(device,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(soc,),
    )
    return DeviceTree(root=root), device


def bus_node(*properties: DeviceTreeProperty) -> DeviceTreeNode:
    return DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=properties,
    )


def reg_region(node_path: str, *, bus_address: int, size: int | None) -> RegRegion:
    return RegRegion(node_path=node_path, index=0, bus_address=bus_address, size=size)


def cell_context(
    source_node_path: str,
    *,
    address_cells: int,
    size_cells: int,
) -> AddressCellContext:
    return AddressCellContext(
        address_cells=address_cells,
        size_cells=size_cells,
        source_node_path=source_node_path,
    )


def cells(name: str, *values: int) -> DeviceTreeProperty:
    return DeviceTreeProperty(name=name, kind=PropertyKind.CELLS, value=values)


def ranges(*values: int) -> DeviceTreeProperty:
    return cells("ranges", *values)


if __name__ == "__main__":
    unittest.main()
