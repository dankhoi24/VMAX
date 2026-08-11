import unittest

from app.model.devicetree import (
    DeviceTree,
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
            value=[0x00000000, 0x12340000, 0x00001000],
        )

        self.assertEqual(prop.raw_hex, "000000001234000000001000")
        self.assertEqual(prop.value, (0x00000000, 0x12340000, 0x00001000))
        self.assertEqual(
            prop.to_dict(),
            {
                "name": "reg",
                "raw_hex": "000000001234000000001000",
                "kind": "cells",
                "value": [0x00000000, 0x12340000, 0x00001000],
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
                ),
            ),
        )
        soc = DeviceTreeNode(
            name="soc",
            path="/soc",
            parent_path="/",
            children=(uart,),
        )
        root = DeviceTreeNode(name="/", path="/", children=(soc,))
        tree = DeviceTree(root=root)

        self.assertEqual(tree.node_count, 3)
        self.assertEqual(uart.full_name, "uart@1000")
        self.assertIs(tree.get_node("/soc/uart@1000"), uart)
        self.assertIs(uart.get_property("compatible"), uart.properties[0])
        self.assertEqual(uart.to_dict()["parent_path"], "/soc")
        self.assertEqual(
            root.to_dict()["children"][0]["children"][0]["id"],
            "/soc/uart@1000",
        )

    def test_parse_result_reports_success_and_node_count(self) -> None:
        root = DeviceTreeNode(name="/", path="/")
        tree = DeviceTree(root=root)
        result = ParseResult(tree=tree, source="board.dtb", warnings=["best effort"])

        self.assertTrue(result.ok)
        self.assertEqual(result.node_count, 1)
        self.assertIs(result.root, root)
        self.assertEqual(result.to_dict()["source"], "board.dtb")
        self.assertEqual(result.to_dict()["tree"]["root"]["path"], "/")

    def test_property_values_are_limited_and_immutable(self) -> None:
        string_list = DeviceTreeProperty(
            name="compatible",
            raw_bytes=b"vendor,device\x00vendor,fallback\x00",
            kind="string_list",
            value=["vendor,device", "vendor,fallback"],
        )
        boolean = DeviceTreeProperty(
            name="dma-coherent",
            kind=PropertyKind.BOOLEAN,
            value=True,
        )
        unknown = DeviceTreeProperty(name="vendor,data", raw_bytes=b"\x01\x02")

        self.assertEqual(string_list.kind, PropertyKind.STRING_LIST)
        self.assertEqual(string_list.value, ("vendor,device", "vendor,fallback"))
        self.assertEqual(string_list.to_dict()["value"], ["vendor,device", "vendor,fallback"])
        self.assertTrue(boolean.value)
        self.assertIsNone(unknown.value)

        with self.assertRaises(TypeError):
            DeviceTreeProperty(name="bad", value=object())

    def test_invalid_contract_inputs_fail_fast(self) -> None:
        with self.assertRaises(ValueError):
            DeviceTreeProperty(name="")

        with self.assertRaises(ValueError):
            DeviceTreeNode(name="soc", path="soc")

        with self.assertRaises(ValueError):
            DeviceTree(root=DeviceTreeNode(name="soc", path="/soc"))


if __name__ == "__main__":
    unittest.main()
