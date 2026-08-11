import tempfile
import unittest
from pathlib import Path

from app.model.devicetree import PropertyKind
from app.parsers.devicetree import LibFdtDeviceTreeParser


class FakeProperty(bytearray):
    def __init__(self, name: str, value: bytes) -> None:
        super().__init__(value)
        self.name = name


class FakeFdt:
    def __init__(self, data: bytes) -> None:
        if data == b"bad":
            raise ValueError("bad fdt")

        self._names = {
            0: "",
            1: "soc",
            2: "uart@1000",
            3: "i2c@2000",
        }
        self._children = {
            0: [1],
            1: [2, 3],
            2: [],
            3: [],
        }
        self._properties = {
            0: [
                ("model", b"Test Board\x00"),
                ("compatible", b"test,board\x00test,fallback\x00"),
            ],
            1: [
                ("#address-cells", bytes.fromhex("00000002")),
                ("ranges", b""),
            ],
            2: [
                ("compatible", b"test,uart\x00"),
                ("reg", bytes.fromhex("000000000000100000000100")),
                ("dma-coherent", b""),
            ],
            3: [],
        }
        self._prop_offsets: dict[int, tuple[int, int]] = {}
        offset = 100
        for node_offset, properties in self._properties.items():
            for prop_index, _prop in enumerate(properties):
                self._prop_offsets[offset] = (node_offset, prop_index)
                offset += 1

    def path_offset(self, path: str) -> int:
        if path != "/":
            raise ValueError(f"unsupported path: {path}")
        return 0

    def get_name(self, node_offset: int) -> str:
        return self._names[node_offset]

    def first_property_offset(self, node_offset: int, quiet=()) -> int:
        if not self._properties[node_offset]:
            return -1
        return self._property_offset(node_offset, 0)

    def next_property_offset(self, prop_offset: int, quiet=()) -> int:
        node_offset, prop_index = self._prop_offsets[prop_offset]
        next_index = prop_index + 1
        if next_index >= len(self._properties[node_offset]):
            return -1
        return self._property_offset(node_offset, next_index)

    def get_property_by_offset(self, prop_offset: int) -> FakeProperty:
        node_offset, prop_index = self._prop_offsets[prop_offset]
        name, value = self._properties[node_offset][prop_index]
        return FakeProperty(name, value)

    def first_subnode(self, node_offset: int, quiet=()) -> int:
        children = self._children[node_offset]
        return children[0] if children else -1

    def next_subnode(self, node_offset: int, quiet=()) -> int:
        parent_offset = self._parent_offset(node_offset)
        siblings = self._children[parent_offset]
        next_index = siblings.index(node_offset) + 1
        if next_index >= len(siblings):
            return -1
        return siblings[next_index]

    def _property_offset(self, node_offset: int, prop_index: int) -> int:
        for prop_offset, pair in self._prop_offsets.items():
            if pair == (node_offset, prop_index):
                return prop_offset
        raise AssertionError("missing fake property offset")

    def _parent_offset(self, node_offset: int) -> int:
        for parent_offset, children in self._children.items():
            if node_offset in children:
                return parent_offset
        raise AssertionError("missing fake parent offset")


class FakeLibFdtModule:
    QUIET_NOTFOUND = (1,)

    def Fdt(self, data: bytes) -> FakeFdt:
        return FakeFdt(data)


class LibFdtDeviceTreeParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = LibFdtDeviceTreeParser(libfdt_module=FakeLibFdtModule())

    def test_parse_bytes_converts_fdt_tree_to_domain_model(self) -> None:
        result = self.parser.parse_bytes(b"fake dtb", source="sample.dtb")

        self.assertTrue(result.ok)
        self.assertEqual(result.source, "sample.dtb")
        self.assertEqual(result.node_count, 4)

        root = result.root
        self.assertIsNotNone(root)
        self.assertEqual(root.name, "/")
        self.assertEqual(root.path, "/")
        self.assertEqual(root.get_property("model").value, "Test Board")
        self.assertEqual(root.get_property("compatible").kind, PropertyKind.STRING_LIST)

        uart = result.tree.get_node("/soc/uart@1000")
        self.assertEqual(uart.name, "uart")
        self.assertEqual(uart.unit_address, "1000")
        self.assertEqual(uart.parent_path, "/soc")
        self.assertEqual(uart.get_property("compatible").value, ("test,uart",))
        self.assertEqual(uart.get_property("reg").kind, PropertyKind.CELLS)
        self.assertEqual(uart.get_property("dma-coherent").kind, PropertyKind.BOOLEAN)

        soc = result.tree.get_node("/soc")
        self.assertEqual(soc.get_property("ranges").value, ())

    def test_parse_reads_dtb_file_and_sets_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "board.dtb"
            path.write_bytes(b"fake dtb")

            result = self.parser.parse(path)

        self.assertTrue(result.ok)
        self.assertEqual(result.source, str(path))

    def test_parse_reports_file_read_errors(self) -> None:
        result = self.parser.parse("missing.dtb")

        self.assertFalse(result.ok)
        self.assertEqual(result.node_count, 0)
        self.assertIn("Failed to read DTB", result.errors[0])

    def test_parse_reports_libfdt_errors(self) -> None:
        result = self.parser.parse_bytes(b"bad", source="bad.dtb")

        self.assertFalse(result.ok)
        self.assertEqual(result.source, "bad.dtb")
        self.assertIn("Failed to parse DTB with pylibfdt", result.errors[0])


if __name__ == "__main__":
    unittest.main()
