import tempfile
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
        self.paths: list[Path] = []

    def collect_from_file(self, path: str | Path) -> ParseResult:
        self.paths.append(Path(path))
        return self.result


def _sample_tree() -> DeviceTree:
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(
                name="compatible",
                raw_bytes=b"test,uart\x00",
                kind=PropertyKind.STRING_LIST,
                value=("test,uart",),
            ),
            DeviceTreeProperty(
                name="status",
                raw_bytes=b"okay\x00",
                kind=PropertyKind.STRING,
                value="okay",
            ),
        ),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        children=(uart,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(
            DeviceTreeProperty(
                name="model",
                raw_bytes=b"VMAX Test Board\x00",
                kind=PropertyKind.STRING,
                value="VMAX Test Board",
            ),
        ),
        children=(soc,),
    )
    return DeviceTree(root=root)


class FastApiDeviceTreeTest(unittest.TestCase):
    def test_metadata_returns_current_dtb_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dtb_path = Path(temp_dir) / "board.dtb"
            dtb_path.write_bytes(b"fake dtb")
            result = ParseResult(tree=_sample_tree(), source=str(dtb_path))
            collector = FakeCollector(result)
            client = TestClient(
                create_app(
                    devicetree_state=DeviceTreeState(
                        current_path=dtb_path,
                        collector=collector,
                    )
                )
            )

            response = client.get("/api/v1/metadata")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "filename": "board.dtb",
                "file_size": 8,
                "node_count": 3,
                "property_count": 3,
                "warnings": [],
                "errors": [],
            },
        )
        self.assertEqual(collector.paths, [dtb_path])

    def test_devicetree_returns_tree_json(self) -> None:
        result = ParseResult(tree=_sample_tree(), source="board.dtb")
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="board.dtb",
                    collector=FakeCollector(result),
                )
            )
        )

        response = client.get("/api/v1/devicetree")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["node_count"], 3)
        self.assertEqual(body["root"]["path"], "/")
        self.assertEqual(
            body["root"]["children"][0]["children"][0]["path"],
            "/soc/uart@1000",
        )

    def test_devicetree_returns_422_when_parse_failed(self) -> None:
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

        response = client.get("/api/v1/devicetree")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errors"], ["Failed to parse DTB"])

    def test_metadata_reports_missing_current_source(self) -> None:
        client = TestClient(create_app(devicetree_state=DeviceTreeState()))

        response = client.get("/api/v1/metadata")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], None)
        self.assertEqual(
            response.json()["errors"],
            ["No current DTB source configured"],
        )

    def test_openapi_exposes_typed_devicetree_contract(self) -> None:
        client = TestClient(create_app(devicetree_state=DeviceTreeState()))

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("MetadataResponse", schemas)
        self.assertIn("DeviceTreeResponse", schemas)
        self.assertIn("DeviceTreeNodeResponse", schemas)
        self.assertIn("DeviceTreePropertyResponse", schemas)
        self.assertEqual(
            response.json()["paths"]["/api/v1/metadata"]["get"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]["$ref"],
            "#/components/schemas/MetadataResponse",
        )


if __name__ == "__main__":
    unittest.main()
