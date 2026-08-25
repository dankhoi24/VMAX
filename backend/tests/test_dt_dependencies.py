from __future__ import annotations

import unittest

from app.dependency import (
    DependencyEvidenceKind,
    DependencyKind,
    DependencyResolution,
    DeviceTreeDependencyExtractor,
)
from app.dependency.devicetree import PhandleResolver
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)


class DeviceTreeDependencyExtractorTest(unittest.TestCase):
    def test_extracts_generic_phandle_array_dependencies(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "cpg",
                "/soc/clock-controller@e6150000",
                phandle=0x17,
                extra_properties=(
                    cells("#clock-cells", 2),
                    cells("#reset-cells", 1),
                ),
            ),
            _provider(
                "sysc",
                "/soc/system-controller@e6180000",
                phandle=0x21,
                extra_properties=(cells("#power-domain-cells", 0),),
            ),
            _provider(
                "dmac",
                "/soc/dma-controller@e7300000",
                phandle=0x30,
                extra_properties=(cells("#dma-cells", 1),),
            ),
            _provider(
                "ipmmu",
                "/soc/iommu@e6740000",
                phandle=0x35,
                extra_properties=(cells("#iommu-cells", 1),),
            ),
            _device(
                properties=(
                    cells("clocks", 0x17, 12, 4, 0x17, 20, 8),
                    strings("clock-names", "axi", "core"),
                    cells("resets", 0x17, 31),
                    cells("power-domains", 0x21),
                    cells("dmas", 0x30, 1, 0x30, 2),
                    strings("dma-names", "tx", "rx"),
                    cells("iommus", 0x35, 3),
                )
            ),
        )

        references = DeviceTreeDependencyExtractor().extract(tree)
        by_key = {
            (reference.kind, reference.source_property, reference.entry_index):
            reference
            for reference in references
            if reference.consumer_dt_path == DEVICE_PATH
        }

        self.assertEqual(
            by_key[(DependencyKind.CLOCK, "clocks", 0)].provider_dt_path,
            "/soc/clock-controller@e6150000",
        )
        self.assertEqual(
            by_key[(DependencyKind.CLOCK, "clocks", 0)].specifier_cells,
            (12, 4),
        )
        self.assertEqual(by_key[(DependencyKind.CLOCK, "clocks", 0)].name, "axi")
        self.assertEqual(by_key[(DependencyKind.CLOCK, "clocks", 1)].name, "core")
        self.assertEqual(
            by_key[(DependencyKind.CLOCK, "clocks", 1)].specifier_cells,
            (20, 8),
        )
        self.assertEqual(
            by_key[(DependencyKind.RESET, "resets", 0)].specifier_cells,
            (31,),
        )
        self.assertEqual(
            by_key[(DependencyKind.POWER_DOMAIN, "power-domains", 0)].specifier_cells,
            (),
        )
        self.assertEqual(by_key[(DependencyKind.DMA, "dmas", 0)].name, "tx")
        self.assertEqual(by_key[(DependencyKind.DMA, "dmas", 1)].name, "rx")
        self.assertEqual(
            by_key[(DependencyKind.IOMMU, "iommus", 0)].provider_phandle,
            0x35,
        )

        for reference in by_key.values():
            self.assertEqual(reference.resolution, DependencyResolution.RESOLVED)
            self.assertEqual(reference.evidence[0].kind, DependencyEvidenceKind.DECLARED)
            self.assertEqual(reference.evidence[0].source, "devicetree")

    def test_unresolved_provider_preserves_phandle_and_remaining_cells(self) -> None:
        tree = _tree_with_soc(
            _device(properties=(cells("iommus", 0x35, 3),)),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(reference.kind, DependencyKind.IOMMU)
        self.assertIsNone(reference.provider_dt_path)
        self.assertEqual(reference.provider_phandle, 0x35)
        self.assertEqual(reference.specifier_cells, (3,))
        self.assertEqual(reference.resolution, DependencyResolution.UNRESOLVED)
        self.assertIn("0x35", reference.evidence[0].message or "")

    def test_missing_provider_cell_count_marks_reference_unavailable(self) -> None:
        tree = _tree_with_soc(
            _provider("cpg", "/soc/clock-controller@e6150000", phandle=0x17),
            _device(properties=(cells("clocks", 0x17, 12, 4),)),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(reference.provider_dt_path, "/soc/clock-controller@e6150000")
        self.assertEqual(reference.provider_phandle, 0x17)
        self.assertEqual(reference.specifier_cells, (12, 4))
        self.assertEqual(reference.resolution, DependencyResolution.UNAVAILABLE)
        self.assertIn("#clock-cells", reference.evidence[0].message or "")

    def test_duplicate_provider_phandle_marks_reference_ambiguous(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "clock-a",
                "/soc/clock-controller@0",
                phandle=0x17,
                extra_properties=(cells("#clock-cells", 1),),
            ),
            _provider(
                "clock-b",
                "/soc/clock-controller@1",
                phandle=0x17,
                extra_properties=(cells("#clock-cells", 1),),
            ),
            _device(properties=(cells("clocks", 0x17, 12),)),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertIsNone(reference.provider_dt_path)
        self.assertEqual(reference.provider_phandle, 0x17)
        self.assertEqual(reference.specifier_cells, (12,))
        self.assertEqual(reference.resolution, DependencyResolution.AMBIGUOUS)

    def test_malformed_dependency_property_is_unavailable(self) -> None:
        tree = _tree_with_soc(
            _device(
                properties=(
                    DeviceTreeProperty(
                        name="clocks",
                        raw_bytes=b"\x00",
                        kind=PropertyKind.UNKNOWN,
                    ),
                )
            ),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(reference.kind, DependencyKind.CLOCK)
        self.assertEqual(reference.source_property, "clocks")
        self.assertEqual(reference.resolution, DependencyResolution.UNAVAILABLE)

    def test_interrupts_use_inherited_interrupt_parent(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "gic",
                "/soc/interrupt-controller@f1000000",
                phandle=0x1,
                extra_properties=(cells("#interrupt-cells", 3),),
            ),
            _device(
                properties=(
                    cells("interrupts", 0, 150, 4, 0, 151, 4),
                    strings("interrupt-names", "main", "wake"),
                )
            ),
            soc_properties=(cells("interrupt-parent", 0x1),),
        )

        references = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(len(references), 2)
        self.assertEqual(references[0].kind, DependencyKind.INTERRUPT)
        self.assertEqual(references[0].provider_dt_path, "/soc/interrupt-controller@f1000000")
        self.assertEqual(references[0].provider_phandle, 0x1)
        self.assertEqual(references[0].entry_index, 0)
        self.assertEqual(references[0].name, "main")
        self.assertEqual(references[0].specifier_cells, (0, 150, 4))
        self.assertEqual(references[1].entry_index, 1)
        self.assertEqual(references[1].name, "wake")
        self.assertEqual(references[1].specifier_cells, (0, 151, 4))

    def test_interrupts_extended_takes_precedence_over_interrupts(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "gic",
                "/soc/interrupt-controller@f1000000",
                phandle=0x1,
                extra_properties=(cells("#interrupt-cells", 3),),
            ),
            _device(
                properties=(
                    cells("interrupts", 0, 100, 4),
                    cells("interrupts-extended", 0x1, 0, 200, 4),
                )
            ),
            soc_properties=(cells("interrupt-parent", 0x1),),
        )

        references = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].source_property, "interrupts-extended")
        self.assertEqual(references[0].specifier_cells, (0, 200, 4))

    def test_interrupts_use_implicit_natural_interrupt_parent(self) -> None:
        sensor = DeviceTreeNode(
            name="sensor",
            path="/soc/gpio@e6050000/sensor@0",
            unit_address="0",
            parent_path="/soc/gpio@e6050000",
            properties=(cells("interrupts", 7, 4),),
        )
        gpio = DeviceTreeNode(
            name="gpio",
            path="/soc/gpio@e6050000",
            unit_address="e6050000",
            parent_path="/soc",
            properties=(
                DeviceTreeProperty(name="interrupt-controller", raw_bytes=b""),
                cells("#interrupt-cells", 2),
            ),
            children=(sensor,),
        )
        tree = _tree_with_soc(gpio)

        references = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].consumer_dt_path, sensor.path)
        self.assertEqual(references[0].provider_dt_path, gpio.path)
        self.assertIsNone(references[0].provider_phandle)
        self.assertEqual(references[0].specifier_cells, (7, 4))
        self.assertEqual(references[0].resolution, DependencyResolution.RESOLVED)

    def test_interrupts_extended_supports_multiple_providers(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "gic",
                "/soc/interrupt-controller@f1000000",
                phandle=0x1,
                extra_properties=(cells("#interrupt-cells", 3),),
            ),
            _provider(
                "gpio",
                "/soc/gpio@e6050000",
                phandle=0x44,
                extra_properties=(cells("#interrupt-cells", 2),),
            ),
            _device(
                properties=(
                    cells("interrupts-extended", 0x1, 0, 150, 4, 0x44, 7, 2),
                    strings("interrupt-names", "main", "gpio"),
                )
            ),
        )

        references = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(len(references), 2)
        self.assertEqual(references[0].source_property, "interrupts-extended")
        self.assertEqual(references[0].provider_dt_path, "/soc/interrupt-controller@f1000000")
        self.assertEqual(references[0].specifier_cells, (0, 150, 4))
        self.assertEqual(references[1].provider_dt_path, "/soc/gpio@e6050000")
        self.assertEqual(references[1].specifier_cells, (7, 2))

    def test_partial_phandle_array_entry_is_unavailable(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "cpg",
                "/soc/clock-controller@e6150000",
                phandle=0x17,
                extra_properties=(cells("#clock-cells", 2),),
            ),
            _device(properties=(cells("clocks", 0x17, 12),)),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(reference.kind, DependencyKind.CLOCK)
        self.assertEqual(reference.provider_dt_path, "/soc/clock-controller@e6150000")
        self.assertEqual(reference.provider_phandle, 0x17)
        self.assertEqual(reference.specifier_cells, (12,))
        self.assertEqual(reference.resolution, DependencyResolution.UNAVAILABLE)
        self.assertIn("partial entry", reference.evidence[0].message or "")

    def test_partial_interrupts_entry_is_unavailable(self) -> None:
        tree = _tree_with_soc(
            _provider(
                "gic",
                "/soc/interrupt-controller@f1000000",
                phandle=0x1,
                extra_properties=(cells("#interrupt-cells", 3),),
            ),
            _device(properties=(cells("interrupts", 0, 150),)),
            soc_properties=(cells("interrupt-parent", 0x1),),
        )

        (reference,) = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(reference.kind, DependencyKind.INTERRUPT)
        self.assertEqual(reference.source_property, "interrupts")
        self.assertEqual(reference.provider_dt_path, "/soc/interrupt-controller@f1000000")
        self.assertEqual(reference.specifier_cells, (0, 150))
        self.assertEqual(reference.resolution, DependencyResolution.UNAVAILABLE)
        self.assertIn("partial entry", reference.evidence[0].message or "")

    def test_phandle_resolver_supports_linux_phandle(self) -> None:
        provider = _provider(
            "ipmmu",
            "/soc/iommu@e6740000",
            phandle=None,
            extra_properties=(
                cells("linux,phandle", 0x35),
                cells("#iommu-cells", 1),
            ),
        )
        tree = _tree_with_soc(provider)

        resolved = PhandleResolver.from_tree(tree).resolve(0x35)

        self.assertEqual(resolved, (provider,))

    def test_phandle_resolver_deduplicates_legacy_alias_on_same_node(self) -> None:
        provider = _provider(
            "cpg",
            "/soc/clock-controller@e6150000",
            phandle=0x17,
            extra_properties=(
                cells("linux,phandle", 0x17),
                cells("#clock-cells", 1),
            ),
        )
        tree = _tree_with_soc(
            provider,
            _device(properties=(cells("clocks", 0x17, 12),)),
        )

        references = DeviceTreeDependencyExtractor().extract(tree)

        self.assertEqual(PhandleResolver.from_tree(tree).resolve(0x17), (provider,))
        self.assertEqual(references[0].resolution, DependencyResolution.RESOLVED)
        self.assertEqual(references[0].provider_dt_path, provider.path)


DEVICE_PATH = "/soc/cnn@e2200000"


def _tree_with_soc(
    *children: DeviceTreeNode,
    soc_properties: tuple[DeviceTreeProperty, ...] = (),
) -> DeviceTree:
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=soc_properties,
        children=children,
    )
    root = DeviceTreeNode(name="/", path="/", children=(soc,))
    return DeviceTree(root=root)


def _provider(
    name: str,
    path: str,
    *,
    phandle: int | None,
    extra_properties: tuple[DeviceTreeProperty, ...] = (),
) -> DeviceTreeNode:
    properties = extra_properties
    if phandle is not None:
        properties = (cells("phandle", phandle), *properties)

    return DeviceTreeNode(
        name=name,
        path=path,
        parent_path="/soc",
        properties=properties,
    )


def _device(
    *,
    properties: tuple[DeviceTreeProperty, ...],
) -> DeviceTreeNode:
    return DeviceTreeNode(
        name="cnn",
        path=DEVICE_PATH,
        unit_address="e2200000",
        parent_path="/soc",
        properties=properties,
    )


def cells(name: str, *values: int) -> DeviceTreeProperty:
    raw = b"".join(value.to_bytes(4, byteorder="big") for value in values)
    return DeviceTreeProperty(
        name=name,
        raw_bytes=raw,
        kind=PropertyKind.CELLS,
        value=values,
    )


def strings(name: str, *values: str) -> DeviceTreeProperty:
    raw = b"".join(value.encode("utf-8") + b"\x00" for value in values)
    kind = PropertyKind.STRING if len(values) == 1 else PropertyKind.STRING_LIST
    value: str | tuple[str, ...] = values[0] if len(values) == 1 else values
    return DeviceTreeProperty(
        name=name,
        raw_bytes=raw,
        kind=kind,
        value=value,
    )


if __name__ == "__main__":
    unittest.main()
