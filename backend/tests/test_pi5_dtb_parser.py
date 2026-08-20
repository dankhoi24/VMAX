import importlib.util
import unittest
from pathlib import Path

from app.parsers.devicetree import LibFdtDeviceTreeParser


class LibFdtDeviceTreeParserPi5SmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = LibFdtDeviceTreeParser()
        self.pi5_dtb_path = Path(__file__).resolve().parent / "fixtures" / "bcm2712-rpi-5-b.dtb"

    def test_parse_pi5_dtb_smoke_test(self) -> None:
        # Parse the Pi 5 DTB file
        result = self.parser.parse(self.pi5_dtb_path)

        # Assert result is ok
        self.assertTrue(result.ok, f"Failed to parse Pi 5 DTB: {result.errors}")

        # Assert that the model is Raspberry Pi 5
        model_prop = result.root.get_property("model")
        self.assertIsNotNone(model_prop)
        self.assertEqual(model_prop.value, "Raspberry Pi 5")

        # Assert root #address-cells and #size-cells
        address_cells_prop = result.root.get_property("#address-cells")
        self.assertIsNotNone(address_cells_prop)
        self.assertEqual(address_cells_prop.value, (2,))

        size_cells_prop = result.root.get_property("#size-cells")
        self.assertIsNotNone(size_cells_prop)
        self.assertEqual(size_cells_prop.value, (2,))

        # Assert reasonable node count (should be significantly more than minimal dtb)
        # Minimal DTB has 3 nodes, Pi 5 should have many more
        self.assertGreater(result.node_count, 10, "Node count should be significantly higher for Pi 5 DTB")

    @unittest.skipUnless(
        importlib.util.find_spec("libfdt") is not None,
        "pylibfdt is not installed",
    )
    def test_parse_pi5_dtb_with_real_pylibfdt(self) -> None:
        # This is a more comprehensive test using the real pylibfdt
        result = self.parser.parse(self.pi5_dtb_path)

        # Verify the parse was successful
        self.assertTrue(result.ok, f"Failed to parse Pi 5 DTB: {result.errors}")

        # Verify model name
        model_prop = result.root.get_property("model")
        self.assertIsNotNone(model_prop)
        self.assertEqual(model_prop.value, "Raspberry Pi 5")

        # Verify root address and size cells
        address_cells_prop = result.root.get_property("#address-cells")
        self.assertIsNotNone(address_cells_prop)
        self.assertEqual(address_cells_prop.value, (2,))

        size_cells_prop = result.root.get_property("#size-cells")
        self.assertIsNotNone(size_cells_prop)
        self.assertEqual(size_cells_prop.value, (2,))

        # Verify node count is reasonable (Pi 5 should have many nodes)
        self.assertGreater(result.node_count, 50,
                         f"Expected reasonable node count for Pi 5, got {result.node_count}")