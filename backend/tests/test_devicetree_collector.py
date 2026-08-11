import unittest
from pathlib import Path

from app.collectors.devicetree import DeviceTreeCollector
from app.model.devicetree import DeviceTree, DeviceTreeNode, ParseResult


class FakeParser:
    def __init__(self, result: ParseResult) -> None:
        self.result = result
        self.paths: list[str | Path] = []

    def parse(self, path: str | Path) -> ParseResult:
        self.paths.append(path)
        return self.result


class DeviceTreeCollectorTest(unittest.TestCase):
    def test_collect_from_file_delegates_to_injected_parser(self) -> None:
        result = ParseResult(
            tree=DeviceTree(root=DeviceTreeNode(name="/", path="/")),
            source="board.dtb",
        )
        parser = FakeParser(result)
        collector = DeviceTreeCollector(parser=parser)

        collected = collector.collect_from_file("board.dtb")

        self.assertIs(collected, result)
        self.assertEqual(parser.paths, ["board.dtb"])

    def test_collect_from_file_preserves_path_objects(self) -> None:
        result = ParseResult(
            tree=DeviceTree(root=DeviceTreeNode(name="/", path="/")),
            source="board.dtb",
        )
        parser = FakeParser(result)
        collector = DeviceTreeCollector(parser=parser)
        path = Path("samples/board.dtb")

        collector.collect_from_file(path)

        self.assertEqual(parser.paths, [path])

    def test_collect_from_file_returns_parser_errors_unchanged(self) -> None:
        result = ParseResult(
            tree=None,
            source="missing.dtb",
            errors=("Failed to read DTB",),
        )
        collector = DeviceTreeCollector(parser=FakeParser(result))

        collected = collector.collect_from_file("missing.dtb")

        self.assertFalse(collected.ok)
        self.assertEqual(collected.errors, ("Failed to read DTB",))


if __name__ == "__main__":
    unittest.main()
