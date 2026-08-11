import unittest

from app.model.devicetree import (
    DeviceTreeNode,
    DeviceTreeProperty,
    ParseResult,
    PropertyKind,
)


class DeviceTreeModelTest(unittest.TestCase):
    def test_property_keeps_raw_bytes_and_json_safe_shape(self) -> None:
        prop = DeviceTreeProperty(
            name="reg",
            raw_bytes=bytes.fromhex("000000001234000000001000"),
            kind=PropertyKind.CELLS,
            value=["0x00000000", "0x12340000", "0x00001000"],
            display_value="<0x00000000 0x12340000 0x00001000>",
        )

        self.assertEqual(prop.raw_hex, "000000001234000000001000")
        self.assertEqual(
            prop.to_dict(),
            {
                "name": "reg",
                "raw_hex": "000000001234000000001000",
                "kind": "cells",
                "value": ["0x00000000", "0x12340000", "0x00001000"],
                "display_value": "<0x00000000 0x12340000 0x00001000>",
            },
        )

    def test_node_supports_lookup_and_tree_serialization(self) -> None:
        uart = DeviceTreeNode(
            name="uart",
            path="/soc/uart@1000",
            unit_address="1000",
            parent_path="/soc",
            properties=(
                DeviceTreeProperty(
                    name="compatible",
                    raw_bytes=b"test,uart\x00",
                    kind=PropertyKind.STRING,
                    value="test,uart",
                    display_value='"test,uart"',
                ),
            ),
        )
        root = DeviceTreeNode(name="/", path="/", children=(uart,))

        self.assertEqual(root.node_count, 2)
        self.assertIs(root.find_by_path("/soc/uart@1000"), uart)
        self.assertIs(uart.get_property("compatible"), uart.properties[0])
        self.assertEqual(uart.to_dict()["parent_path"], "/soc")
        self.assertEqual(root.to_dict()["children"][0]["id"], "/soc/uart@1000")

    def test_parse_result_reports_success_and_node_count(self) -> None:
        root = DeviceTreeNode(name="/", path="/")
        result = ParseResult(root=root, source="board.dtb", warnings=["best effort"])

        self.assertTrue(result.ok)
        self.assertEqual(result.node_count, 1)
        self.assertEqual(result.to_dict()["source"], "board.dtb")

    def test_invalid_contract_inputs_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            DeviceTreeProperty(name="")

        with self.assertRaises(ValueError):
            DeviceTreeNode(name="soc", path="soc")


if __name__ == "__main__":
    unittest.main()
