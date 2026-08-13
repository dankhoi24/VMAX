import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    ParseResult,
    PropertyKind,
)
from app.services.devicetree_state import DeviceTreeState


class FakeCollector:
    def __init__(self, result: ParseResult) -> None:
        self.result = result

    def collect_from_file(self, path: str | Path) -> ParseResult:
        return self.result


class FastApiAddressingTest(unittest.TestCase):
    def test_addressing_returns_report_json(self) -> None:
        result = ParseResult(tree=sample_tree(), source="board.dtb")
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="board.dtb",
                    collector=FakeCollector(result),
                )
            )
        )

        response = client.get("/api/v1/addressing")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(
            body["regions"],
            [
                {
                    "node_path": "/soc/uart@1000",
                    "kind": "device",
                    "start": "0x107d001000",
                    "size": "0x100",
                    "end": "0x107d0010ff",
                }
            ],
        )
        self.assertEqual(
            body["mappings"],
            [
                {
                    "node_path": "/soc",
                    "index": 0,
                    "child_address": "0x0",
                    "parent_address": "0x107d000000",
                    "size": "0x100000",
                    "source_property": "ranges",
                }
            ],
        )
        self.assertEqual(body["translations"][0]["node_path"], "/soc/uart@1000")
        self.assertEqual(body["translations"][0]["bus_address"], "0x1000")
        self.assertEqual(body["translations"][0]["cpu_address"], "0x107d001000")
        self.assertEqual(
            body["translations"][0]["translation_path"],
            [
                {
                    "bus_node_path": "/soc",
                    "input_address": "0x1000",
                    "output_address": "0x107d001000",
                    "mapping_index": 0,
                }
            ],
        )

    def test_addressing_serializes_large_addresses_as_hex_strings(self) -> None:
        result = ParseResult(tree=large_address_tree(), source="board.dtb")
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="board.dtb",
                    collector=FakeCollector(result),
                )
            )
        )

        response = client.get("/api/v1/addressing")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["regions"][0]["start"], "0xfffffffffffff000")
        self.assertEqual(body["regions"][0]["end"], "0xffffffffffffffff")
        self.assertEqual(body["mappings"][0]["parent_address"], "0xfffffffffffff000")
        self.assertEqual(body["translations"][0]["cpu_address"], "0xfffffffffffff000")

    def test_addressing_returns_422_when_parse_failed(self) -> None:
        result = ParseResult(
            tree=None,
            source="bad.dtb",
            errors=("Failed to parse DTB",),
        )
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="bad.dtb",
                    collector=FakeCollector(result),
                )
            )
        )

        response = client.get("/api/v1/addressing")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errors"], ["Failed to parse DTB"])

    def test_openapi_exposes_typed_addressing_contract(self) -> None:
        client = TestClient(create_app(devicetree_state=DeviceTreeState()))

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("AddressingReportResponse", schemas)
        self.assertIn("MemoryRegionResponse", schemas)
        self.assertIn("TranslatedAddressRangeResponse", schemas)
        self.assertEqual(
            schemas["MemoryRegionResponse"]["properties"]["start"]["type"],
            "string",
        )
        self.assertEqual(
            schemas["RangeMappingResponse"]["properties"]["parent_address"]["type"],
            "string",
        )
        self.assertEqual(
            schemas["TranslatedAddressRangeResponse"]["properties"]["bus_address"][
                "type"
            ],
            "string",
        )
        self.assertEqual(
            response.json()["paths"]["/api/v1/addressing"]["get"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]["$ref"],
            "#/components/schemas/AddressingReportResponse",
        )


def sample_tree() -> DeviceTree:
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
        properties=(cells("reg", 0x1000, 0x100),),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(
            cells("#address-cells", 1),
            cells("#size-cells", 1),
            cells("ranges", 0, 0x10, 0x7D000000, 0x100000),
        ),
        children=(uart,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(soc,),
    )
    return DeviceTree(root=root)


def large_address_tree() -> DeviceTree:
    device = DeviceTreeNode(
        name="device",
        path="/soc/device@0",
        unit_address="0",
        parent_path="/soc",
        properties=(cells("reg", 0, 0x1000),),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(
            cells("#address-cells", 1),
            cells("#size-cells", 1),
            cells("ranges", 0, 0xFFFFFFFF, 0xFFFFF000, 0x1000),
        ),
        children=(device,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(soc,),
    )
    return DeviceTree(root=root)


def cells(name: str, *values: int) -> DeviceTreeProperty:
    return DeviceTreeProperty(name=name, kind=PropertyKind.CELLS, value=values)


if __name__ == "__main__":
    unittest.main()
