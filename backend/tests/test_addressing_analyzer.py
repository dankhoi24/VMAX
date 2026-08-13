import unittest

from app.addressing import AddressingAnalyzer
from app.model.addressing import MemoryRegionKind
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


class AddressingAnalyzerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = AddressingAnalyzer()

    def test_analyze_builds_complete_addressing_report(self) -> None:
        report = self.analyzer.analyze(sample_addressing_tree())

        self.assertEqual(report.warnings, ())
        self.assertEqual(
            [
                (region.node_path, region.kind, region.start, region.size)
                for region in report.regions
            ],
            [
                ("/memory@0", MemoryRegionKind.RAM, 0, 0x80000000),
                (
                    "/reserved-memory/cma@40000000",
                    MemoryRegionKind.RESERVED,
                    0x40000000,
                    0x01000000,
                ),
                ("/soc/uart@1000", MemoryRegionKind.DEVICE, 0x107D001000, 0x100),
            ],
        )
        self.assertEqual(len(report.mappings), 1)
        self.assertEqual(report.mappings[0].node_path, "/soc")
        self.assertEqual(report.mappings[0].child_address, 0)
        self.assertEqual(report.mappings[0].parent_address, 0x107D000000)
        self.assertEqual(report.mappings[0].size, 0x100000)
        self.assertEqual(
            [
                (
                    translation.node_path,
                    translation.bus_address,
                    translation.cpu_address,
                    translation.end,
                )
                for translation in report.translations
            ],
            [
                ("/memory@0", 0, 0, 0x7FFFFFFF),
                (
                    "/reserved-memory/cma@40000000",
                    0x40000000,
                    0x40000000,
                    0x40FFFFFF,
                ),
                ("/soc/uart@1000", 0x1000, 0x107D001000, 0x107D0010FF),
            ],
        )
        self.assertEqual(
            [
                (
                    step.bus_node_path,
                    step.input_address,
                    step.output_address,
                    step.mapping_index,
                )
                for step in report.translations[2].translation_path
            ],
            [("/soc", 0x1000, 0x107D001000, 0)],
        )

    def test_report_warnings_are_deduplicated(self) -> None:
        uart = DeviceTreeNode(
            name="uart",
            path="/soc/uart@1000",
            unit_address="1000",
            parent_path="/soc",
            properties=(reg(0, 0x1000, 0x100),),
        )
        soc = DeviceTreeNode(
            name="soc",
            path="/soc",
            parent_path="/",
            properties=(ranges(),),
            children=(uart,),
        )
        root = DeviceTreeNode(
            name="/",
            path="/",
            properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
            children=(soc,),
        )

        report = self.analyzer.analyze(DeviceTree(root=root))

        self.assertEqual(
            [warning.code for warning in report.warnings],
            ["DEFAULT_ADDRESS_CELLS", "DEFAULT_SIZE_CELLS"],
        )
        self.assertEqual([warning.node_path for warning in report.warnings], ["/soc", "/soc"])

    def test_sizeless_reg_is_not_classified_as_memory_region(self) -> None:
        cpu = DeviceTreeNode(
            name="cpu",
            path="/cpus/cpu@0",
            unit_address="0",
            parent_path="/cpus",
            properties=(reg(0),),
        )
        cpus = DeviceTreeNode(
            name="cpus",
            path="/cpus",
            parent_path="/",
            properties=(
                cells("#address-cells", 1),
                cells("#size-cells", 0),
                ranges(),
            ),
            children=(cpu,),
        )
        root = DeviceTreeNode(
            name="/",
            path="/",
            properties=(cells("#address-cells", 1), cells("#size-cells", 1)),
            children=(cpus,),
        )

        report = self.analyzer.analyze(DeviceTree(root=root))

        self.assertEqual(report.regions, ())
        self.assertEqual(len(report.translations), 1)
        self.assertEqual(report.translations[0].node_path, "/cpus/cpu@0")
        self.assertEqual(report.translations[0].cpu_address, 0)
        self.assertEqual(
            [warning.code for warning in report.warnings],
            ["NON_MEMORY_REG_SEMANTICS"],
        )


def sample_addressing_tree() -> DeviceTree:
    memory = DeviceTreeNode(
        name="memory",
        path="/memory@0",
        unit_address="0",
        parent_path="/",
        properties=(reg(0, 0, 0x80000000),),
    )
    reserved_cma = DeviceTreeNode(
        name="cma",
        path="/reserved-memory/cma@40000000",
        unit_address="40000000",
        parent_path="/reserved-memory",
        properties=(reg(0, 0x40000000, 0x01000000),),
    )
    reserved_memory = DeviceTreeNode(
        name="reserved-memory",
        path="/reserved-memory",
        parent_path="/",
        properties=(
            cells("#address-cells", 2),
            cells("#size-cells", 1),
            ranges(),
        ),
        children=(reserved_cma,),
    )
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
        properties=(reg(0x1000, 0x100),),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(
            cells("#address-cells", 1),
            cells("#size-cells", 1),
            ranges(0, 0x10, 0x7D000000, 0x100000),
        ),
        children=(uart,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(memory, reserved_memory, soc),
    )
    return DeviceTree(root=root)


def cells(name: str, *values: int) -> DeviceTreeProperty:
    return DeviceTreeProperty(name=name, kind=PropertyKind.CELLS, value=values)


def reg(*values: int) -> DeviceTreeProperty:
    return cells("reg", *values)


def ranges(*values: int) -> DeviceTreeProperty:
    return cells("ranges", *values)


if __name__ == "__main__":
    unittest.main()
