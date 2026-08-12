import dataclasses
import unittest

from app.model.addressing import (
    AddressCellContext,
    AddressingReport,
    AddressingWarning,
    MemoryRegion,
    MemoryRegionKind,
    RangeMapping,
    RegRegion,
    TranslatedAddressRange,
    TranslationStep,
)


class AddressingModelTest(unittest.TestCase):
    def test_reg_region_end_calculation(self) -> None:
        region = RegRegion(
            node_path="/soc/uart@1000",
            index=0,
            bus_address=0x1000,
            size=0x100,
        )

        self.assertEqual(region.end, 0x10FF)

    def test_reg_region_has_no_end_for_unknown_or_zero_size(self) -> None:
        unknown_size = RegRegion(
            node_path="/soc/uart@1000",
            index=0,
            bus_address=0x1000,
            size=None,
        )
        zero_size = RegRegion(
            node_path="/soc/uart@1000",
            index=1,
            bus_address=0x2000,
            size=0,
        )

        self.assertIsNone(unknown_size.end)
        self.assertIsNone(zero_size.end)

    def test_large_python_int_addresses_are_preserved(self) -> None:
        large_address = 1 << 96
        region = RegRegion(
            node_path="/soc/large@0",
            index=0,
            bus_address=large_address,
            size=0x20,
        )

        self.assertEqual(region.bus_address, large_address)
        self.assertEqual(region.end, large_address + 0x1F)

    def test_translated_address_range_end_uses_cpu_address(self) -> None:
        translated = TranslatedAddressRange(
            node_path="/soc/uart@1000",
            bus_address=0x1000,
            cpu_address=0x107D001000,
            size=0x200,
        )

        self.assertEqual(translated.end, 0x107D0011FF)

    def test_translated_address_range_has_no_end_without_cpu_address_or_size(self) -> None:
        without_cpu = TranslatedAddressRange(
            node_path="/soc/uart@1000",
            bus_address=0x1000,
            cpu_address=None,
            size=0x200,
        )
        without_size = TranslatedAddressRange(
            node_path="/soc/uart@1000",
            bus_address=0x1000,
            cpu_address=0x107D001000,
            size=None,
        )
        zero_size = TranslatedAddressRange(
            node_path="/soc/uart@1000",
            bus_address=0x1000,
            cpu_address=0x107D001000,
            size=0,
        )

        self.assertIsNone(without_cpu.end)
        self.assertIsNone(without_size.end)
        self.assertIsNone(zero_size.end)

    def test_memory_region_kind_enum_and_end_calculation(self) -> None:
        ram = MemoryRegion(
            node_path="/memory@40000000",
            kind="ram",
            start=0x40000000,
            size=0x10000000,
        )
        reserved = MemoryRegion(
            node_path="/reserved-memory/linux,cma",
            kind=MemoryRegionKind.RESERVED,
            start=0x50000000,
            size=None,
        )

        self.assertEqual(ram.kind, MemoryRegionKind.RAM)
        self.assertEqual(ram.end, 0x4FFFFFFF)
        self.assertEqual(reserved.kind, MemoryRegionKind.RESERVED)
        self.assertIsNone(reserved.end)

    def test_translation_path_and_warnings_are_immutable_tuples(self) -> None:
        step = TranslationStep(
            bus_node_path="/soc",
            input_address=0x1000,
            output_address=0x107D001000,
            mapping_index=1,
        )
        warning = AddressingWarning(
            code="MISSING_RANGES",
            node_path="/soc/uart@1000",
            message="No ranges mapping found for parent bus",
        )
        translated = TranslatedAddressRange(
            node_path="/soc/uart@1000",
            bus_address=0x1000,
            cpu_address=None,
            size=0x200,
            translation_path=[step],
            warnings=[warning],
        )

        self.assertEqual(translated.translation_path, (step,))
        self.assertEqual(translated.warnings, (warning,))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            translated.size = 0x100

    def test_addressing_report_normalizes_collections_to_tuples(self) -> None:
        region = MemoryRegion(
            node_path="/soc/uart@1000",
            kind=MemoryRegionKind.DEVICE,
            start=0x107D001000,
            size=0x200,
        )
        mapping = RangeMapping(
            node_path="/soc",
            index=0,
            child_address=0x1000,
            parent_address=0x107D001000,
            size=0x200,
        )
        warning = AddressingWarning(
            code="DEFAULT_ADDRESS_CELLS",
            node_path="/soc",
            message="Using default #address-cells",
        )
        report = AddressingReport(
            regions=[region],
            mappings=[mapping],
            translations=[],
            warnings=[warning],
        )

        self.assertEqual(report.regions, (region,))
        self.assertEqual(report.mappings, (mapping,))
        self.assertEqual(report.translations, ())
        self.assertEqual(report.warnings, (warning,))

    def test_address_cell_context_tracks_default_flags(self) -> None:
        context = AddressCellContext(
            address_cells=2,
            size_cells=1,
            source_node_path="/soc",
            used_default_address_cells=True,
            used_default_size_cells=False,
        )

        self.assertEqual(context.address_cells, 2)
        self.assertEqual(context.size_cells, 1)
        self.assertTrue(context.used_default_address_cells)
        self.assertFalse(context.used_default_size_cells)

    def test_invalid_contract_inputs_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            AddressingWarning(code="", node_path="/soc", message="bad")

        with self.assertRaises(ValueError):
            AddressCellContext(
                address_cells=-1,
                size_cells=1,
                source_node_path="/soc",
            )

        with self.assertRaises(ValueError):
            RegRegion(node_path="soc/uart@1000", index=0, bus_address=0, size=1)

        with self.assertRaises(ValueError):
            RangeMapping(
                node_path="/soc",
                index=-1,
                child_address=0,
                parent_address=0,
                size=1,
            )

        with self.assertRaises(ValueError):
            TranslationStep(
                bus_node_path="/soc",
                input_address=0,
                output_address=0,
                mapping_index=-1,
            )


if __name__ == "__main__":
    unittest.main()
