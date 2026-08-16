import unittest
from pathlib import Path

from app.parsers.devicetree import LibFdtDeviceTreeParser
from app.addressing.analyzer import AddressingAnalyzer
from app.model.addressing import MemoryRegionKind


class Pi5AddressingSemanticTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = LibFdtDeviceTreeParser()
        self.analyzer = AddressingAnalyzer()
        self.pi5_dtb_path = Path(__file__).resolve().parent / "fixtures" / "bcm2712-rpi-5-b.dtb"

    def test_pi5_ram_and_reserved_memory_semantic_validation(self) -> None:
        # Parse the Pi 5 DTB file
        parse_result = self.parser.parse(self.pi5_dtb_path)
        self.assertTrue(parse_result.ok, f"Failed to parse Pi 5 DTB: {parse_result.errors}")

        # Analyze addressing
        report = self.analyzer.analyze(parse_result.tree)

        # Find the RAM region at /memory@0
        ram_region = None
        atf_region = None
        cma_region = None

        for region in report.regions:
            if region.node_path == "/memory@0":
                ram_region = region
            elif region.node_path == "/reserved-memory/atf@0":
                atf_region = region
            elif region.node_path == "/reserved-memory/linux,cma":
                cma_region = region

        # Verify RAM region exists and is correctly classified
        self.assertIsNotNone(ram_region, "RAM region at /memory@0 should exist")
        self.assertEqual(ram_region.kind, MemoryRegionKind.RAM,
                         "RAM region should be classified as RAM")

        # Verify exact RAM properties
        self.assertEqual(ram_region.start, 0x0, "RAM should start at 0x0")
        self.assertEqual(ram_region.size, 0x28000000, "RAM should be 0x28000000 bytes (640 MiB)")
        self.assertEqual(ram_region.end, 0x27FFFFFF, "RAM end address should be 0x27FFFFFF")

        # Verify ATF reserved memory region
        self.assertIsNotNone(atf_region, "ATF reserved memory region should exist")
        self.assertEqual(atf_region.kind, MemoryRegionKind.RESERVED,
                         "ATF reserved memory should be classified as RESERVED")
        self.assertEqual(atf_region.start, 0x0, "ATF reserved memory should start at 0x0")
        self.assertEqual(atf_region.size, 0x80000, "ATF reserved memory should be 0x80000 bytes (512 KiB)")
        self.assertEqual(atf_region.end, 0x7FFFF, "ATF reserved memory end should be 0x7FFFF")

        # Verify that the reserved-memory/linux,cma region does NOT appear in the regions list
        # This is important because it has no static reg property and should not be fabricated
        for region in report.regions:
            self.assertNotEqual(region.node_path, "/reserved-memory/linux,cma",
                             "The linux,cma reserved memory node should not produce a fabricated MemoryRegion "
                             "because it has no static reg property")

    def test_pi5_serial_device_ranges_translation(self) -> None:
        # Parse the Pi 5 DTB file
        parse_result = self.parser.parse(self.pi5_dtb_path)
        self.assertTrue(parse_result.ok, f"Failed to parse Pi 5 DTB: {parse_result.errors}")

        # Analyze addressing
        report = self.analyzer.analyze(parse_result.tree)

        # Find the serial device at /soc@107c000000/serial@7d001000
        SERIAL_PATH = "/soc@107c000000/serial@7d001000"
        SOC_PATH = "/soc@107c000000"

        serial_translation = None
        for translation in report.translations:
            if translation.node_path == SERIAL_PATH:
                serial_translation = translation
                break

        # Verify that we found the serial translation
        self.assertIsNotNone(serial_translation, "Serial device translation should exist")

        # Verify translation properties
        self.assertEqual(serial_translation.bus_address, 0x7d001000, "Bus address should be 0x7d001000")
        self.assertEqual(serial_translation.cpu_address, 0x107d001000, "CPU address should be 0x107d001000")
        self.assertEqual(serial_translation.size, 0x200, "Size should be 0x200")
        self.assertEqual(serial_translation.end, 0x107d0011ff, "End address should be 0x107d0011ff")

        # Verify translation path has exactly one step
        self.assertEqual(len(serial_translation.translation_path), 1,
                        "Translation path should have exactly one step")

        # Verify the single step in the translation path
        step = serial_translation.translation_path[0]
        self.assertEqual(step.bus_node_path, SOC_PATH, "Translation should be from /soc@107c000000")
        self.assertEqual(step.input_address, 0x7d001000, "Input address should be 0x7d001000")
        self.assertEqual(step.output_address, 0x107d001000, "Output address should be 0x107d001000")
        self.assertEqual(step.mapping_index, 0, "Mapping index should be 0")