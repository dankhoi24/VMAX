import unittest

from app.addressing.memory_regions import MemoryRegionClassifier
from app.model.addressing import (
    AddressingWarning,
    MemoryRegionKind,
    TranslatedAddressRange,
)


class MemoryRegionClassifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = MemoryRegionClassifier()

    def test_classifies_root_memory_node_as_ram(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/memory@0",
                bus_address=0,
                cpu_address=0,
                size=0x80000000,
            )
        )

        self.assertEqual(warnings, ())
        self.assertIsNotNone(region)
        self.assertEqual(region.node_path, "/memory@0")
        self.assertEqual(region.kind, MemoryRegionKind.RAM)
        self.assertEqual(region.start, 0)
        self.assertEqual(region.size, 0x80000000)
        self.assertEqual(region.end, 0x7FFFFFFF)

    def test_classifies_root_memory_without_unit_address_as_ram(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/memory",
                bus_address=0,
                cpu_address=0,
                size=0x100000,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.RAM)

    def test_does_not_classify_nested_memory_named_device_as_ram(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/soc/memory@1000",
                bus_address=0x1000,
                cpu_address=0x107D001000,
                size=0x100,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.DEVICE)

    def test_classifies_reserved_memory_descendant_as_reserved(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/reserved-memory/camera@40000000",
                bus_address=0x40000000,
                cpu_address=0x40000000,
                size=0x04000000,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.RESERVED)
        self.assertEqual(region.start, 0x40000000)
        self.assertEqual(region.end, 0x43FFFFFF)

    def test_does_not_auto_classify_nested_reserved_descendant_as_reserved(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/reserved-memory/vendor/camera@40000000",
                bus_address=0x40000000,
                cpu_address=0x40000000,
                size=0x1000,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.DEVICE)

    def test_classifies_translated_device_resource_as_device(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/soc/uart@1000",
                bus_address=0x1000,
                cpu_address=0x107D001000,
                size=0x100,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.DEVICE)
        self.assertEqual(region.start, 0x107D001000)
        self.assertEqual(region.size, 0x100)
        self.assertEqual(region.end, 0x107D0010FF)

    def test_uses_cpu_address_not_bus_address(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/soc/device@1000",
                bus_address=0x1000,
                cpu_address=0x90001000,
                size=0x200,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.start, 0x90001000)

    def test_supports_40_bit_region_start_and_derived_end(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/soc/device@1000",
                bus_address=0x1000,
                cpu_address=0x107D001000,
                size=0x1000,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.start, 0x107D001000)
        self.assertEqual(region.end, 0x107D001FFF)

    def test_preserves_unknown_size_without_fabricating_end(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/cpus/cpu@0",
                bus_address=0,
                cpu_address=0,
                size=None,
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(region.kind, MemoryRegionKind.DEVICE)
        self.assertIsNone(region.size)
        self.assertIsNone(region.end)

    def test_unresolved_translation_creates_no_memory_region(self) -> None:
        source_warning = AddressingWarning(
            code="MISSING_RANGES",
            node_path="/soc",
            message="Bus node has no ranges property",
        )

        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/soc/uart@1000",
                bus_address=0x1000,
                cpu_address=None,
                size=0x100,
                warnings=(source_warning,),
            )
        )

        self.assertIsNone(region)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MISSING_RANGES", "MEMORY_REGION_TRANSLATION_UNRESOLVED"],
        )

    def test_container_nodes_create_no_memory_region(self) -> None:
        region, warnings = self.classifier.classify(
            translated_range(
                node_path="/reserved-memory",
                bus_address=0,
                cpu_address=0,
                size=0x1000,
            )
        )

        self.assertIsNone(region)
        self.assertEqual(
            [warning.code for warning in warnings],
            ["UNSUPPORTED_MEMORY_REGION_NODE"],
        )

    def test_classifies_many_ranges_and_preserves_order(self) -> None:
        regions, warnings = self.classifier.classify_many(
            (
                translated_range(
                    node_path="/memory@0",
                    bus_address=0,
                    cpu_address=0,
                    size=0x1000,
                ),
                translated_range(
                    node_path="/reserved-memory/cma@80000000",
                    bus_address=0x80000000,
                    cpu_address=0x80000000,
                    size=0x1000,
                ),
                translated_range(
                    node_path="/soc/uart@1000",
                    bus_address=0x1000,
                    cpu_address=0x107D001000,
                    size=0x100,
                ),
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(
            [(region.node_path, region.kind) for region in regions],
            [
                ("/memory@0", MemoryRegionKind.RAM),
                ("/reserved-memory/cma@80000000", MemoryRegionKind.RESERVED),
                ("/soc/uart@1000", MemoryRegionKind.DEVICE),
            ],
        )

    def test_classifies_same_memory_node_multiple_ranges_as_ram(self) -> None:
        regions, warnings = self.classifier.classify_many(
            (
                translated_range(
                    node_path="/memory@0",
                    bus_address=0,
                    cpu_address=0,
                    size=0x80000000,
                ),
                translated_range(
                    node_path="/memory@0",
                    bus_address=0x1_00000000,
                    cpu_address=0x1_00000000,
                    size=0x40000000,
                ),
            )
        )

        self.assertEqual(warnings, ())
        self.assertEqual(
            [(region.kind, region.start, region.size) for region in regions],
            [
                (MemoryRegionKind.RAM, 0x0, 0x80000000),
                (MemoryRegionKind.RAM, 0x1_00000000, 0x40000000),
            ],
        )

    def test_classify_many_skips_unresolved_regions_and_collects_warnings(self) -> None:
        regions, warnings = self.classifier.classify_many(
            (
                translated_range(
                    node_path="/soc/uart@1000",
                    bus_address=0x1000,
                    cpu_address=0x107D001000,
                    size=0x100,
                ),
                translated_range(
                    node_path="/soc/i2c@2000",
                    bus_address=0x2000,
                    cpu_address=None,
                    size=0x100,
                ),
            )
        )

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].node_path, "/soc/uart@1000")
        self.assertEqual(
            [warning.code for warning in warnings],
            ["MEMORY_REGION_TRANSLATION_UNRESOLVED"],
        )


def translated_range(
    *,
    node_path: str,
    bus_address: int,
    cpu_address: int | None,
    size: int | None,
    warnings: tuple[AddressingWarning, ...] = (),
) -> TranslatedAddressRange:
    return TranslatedAddressRange(
        node_path=node_path,
        bus_address=bus_address,
        cpu_address=cpu_address,
        size=size,
        warnings=warnings,
    )


if __name__ == "__main__":
    unittest.main()
