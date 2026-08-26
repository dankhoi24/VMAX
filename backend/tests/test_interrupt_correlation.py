from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from app.dependency import (
    DependencyEvidence,
    DependencyEvidenceKind,
    DependencyKind,
    DependencyReference,
    DependencyResolution,
)
from app.interrupts import (
    InterruptCorrelation,
    InterruptCorrelationReport,
    InterruptCorrelationResolution,
    InterruptCorrelationService,
    InterruptCorrelationWarning,
    InterruptIdentity,
    InterruptIdentityExtractor,
    InterruptMatchMethod,
)
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    PropertyKind,
)
from app.runtime import RuntimeInterrupt


GIC_PATH = "/soc/interrupt-controller@f1000000"
SECOND_GIC_PATH = "/soc/interrupt-controller@f2000000"
GPIO_PATH = "/soc/gpio@e6050000"
IMR_PATH = "/soc/imr@e6260000"


class InterruptCorrelationTest(unittest.TestCase):
    def test_gic_interrupt_specifier_yields_canonical_hwirq_identity(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))

        identities, warnings = InterruptIdentityExtractor().dt_identities(
            dependency,
            _tree(gic_interrupt_cells=4),
        )

        self.assertEqual(warnings, ())
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].controller_key, "gic")
        self.assertEqual(identities[0].hardware_irq, 182)
        self.assertEqual(identities[0].trigger, "level")
        self.assertEqual(
            _metadata(identities[0], "gic_hwirq_rule"),
            "gic_intid",
        )
        self.assertEqual(
            _metadata(identities[0], "specifier_cell_count"),
            3,
        )

    def test_gic_four_cell_interrupt_specifier_is_supported(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4, 0))

        identities, warnings = InterruptIdentityExtractor().dt_identities(
            dependency,
            _tree(),
        )

        self.assertEqual(warnings, ())
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0].hardware_irq, 182)
        self.assertEqual(
            _metadata(identities[0], "specifier_cell_count"),
            4,
        )
        self.assertEqual(
            _metadata(identities[0], "ppi_partition_phandle"),
            0,
        )

    def test_correlates_gic_dependency_to_runtime_interrupt(self) -> None:
        dependency = _interrupt_dependency(name="main", specifier_cells=(0, 150, 4))
        runtime = RuntimeInterrupt(
            irq=182,
            counts=(0, 4291, 0, 0),
            controller="GICv3",
            hardware_irq=182,
            trigger="Level",
            actions=("imr",),
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(runtime,),
        )

        self.assertEqual(report.warnings, ())
        self.assertEqual(len(report.correlations), 1)
        correlation = report.correlations[0]
        self.assertIs(correlation.dependency, dependency)
        self.assertIs(correlation.runtime_interrupt, runtime)
        self.assertEqual(correlation.runtime_candidates, (runtime,))
        self.assertEqual(
            correlation.resolution,
            InterruptCorrelationResolution.RESOLVED,
        )
        self.assertEqual(
            correlation.match_method,
            InterruptMatchMethod.CONTROLLER_HARDWARE_IRQ,
        )

    def test_raw_gic_spi_number_does_not_match_runtime_hwirq(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))
        runtime = RuntimeInterrupt(
            irq=214,
            counts=(1, 0, 0, 0),
            controller="GICv3",
            hardware_irq=150,
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(runtime,),
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNRESOLVED,
        )
        self.assertIsNone(report.correlations[0].runtime_interrupt)

    def test_hwirq_without_supported_controller_does_not_match(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 7, 4))
        runtime = RuntimeInterrupt(
            irq=55,
            counts=(1,),
            controller="gpio",
            hardware_irq=7,
            actions=("imr",),
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(runtime,),
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNRESOLVED,
        )
        self.assertIsNone(report.correlations[0].runtime_interrupt)

    def test_action_only_match_does_not_auto_resolve(self) -> None:
        dependency = _interrupt_dependency(name="imr", specifier_cells=(0, 150, 4))
        runtime = RuntimeInterrupt(
            irq=182,
            counts=(0, 4291, 0, 0),
            controller="GICv3",
            hardware_irq=999,
            actions=("imr",),
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(runtime,),
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNRESOLVED,
        )
        self.assertEqual(report.correlations[0].runtime_candidates, ())

    def test_multiple_runtime_irq_candidates_are_ambiguous(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))
        irq_a = RuntimeInterrupt(
            irq=182,
            counts=(1,),
            controller="GICv3",
            hardware_irq=182,
        )
        irq_b = RuntimeInterrupt(
            irq=300,
            counts=(2,),
            controller="GICv3",
            hardware_irq=182,
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(irq_a, irq_b),
        )

        correlation = report.correlations[0]
        self.assertEqual(correlation.resolution, InterruptCorrelationResolution.AMBIGUOUS)
        self.assertEqual(correlation.runtime_candidates, (irq_a, irq_b))
        self.assertEqual(correlation.warnings[0].code, "RUNTIME_INTERRUPT_MATCH_AMBIGUOUS")
        self.assertEqual(report.warnings[0].code, "RUNTIME_INTERRUPT_MATCH_AMBIGUOUS")

    def test_multiple_gic_domains_do_not_auto_resolve_family_hwirq_match(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))
        runtime = RuntimeInterrupt(
            irq=182,
            counts=(1,),
            controller="GICv3",
            hardware_irq=182,
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(with_second_gic=True),
            dependencies=(dependency,),
            interrupts=(runtime,),
        )

        correlation = report.correlations[0]
        self.assertEqual(
            correlation.resolution,
            InterruptCorrelationResolution.AMBIGUOUS,
        )
        self.assertIsNone(correlation.runtime_interrupt)
        self.assertEqual(correlation.runtime_candidates, (runtime,))
        self.assertEqual(
            correlation.warnings[0].code,
            "DT_INTERRUPT_CONTROLLER_DOMAIN_AMBIGUOUS",
        )

    def test_runtime_interrupt_source_unavailable_is_not_unresolved(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(),
            interrupts_complete=False,
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNAVAILABLE,
        )

    def test_unresolved_dt_dependency_remains_unresolved(self) -> None:
        dependency = _interrupt_dependency(
            provider_dt_path=None,
            specifier_cells=(0, 150, 4),
            resolution=DependencyResolution.UNRESOLVED,
            message="Provider phandle 0x1 was not found",
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(
                RuntimeInterrupt(
                    irq=182,
                    counts=(1,),
                    controller="GICv3",
                    hardware_irq=150,
                ),
            ),
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNRESOLVED,
        )
        self.assertEqual(report.warnings[0].code, "DT_INTERRUPT_DEPENDENCY_NOT_RESOLVED")

    def test_unsupported_interrupt_provider_is_unavailable(self) -> None:
        dependency = _interrupt_dependency(
            provider_dt_path=GPIO_PATH,
            specifier_cells=(7, 4),
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(),
        )

        self.assertEqual(
            report.correlations[0].resolution,
            InterruptCorrelationResolution.UNAVAILABLE,
        )
        self.assertEqual(report.warnings[0].code, "DT_INTERRUPT_PROVIDER_UNSUPPORTED")

    def test_ignores_non_interrupt_dependencies(self) -> None:
        dependency = DependencyReference(
            kind=DependencyKind.CLOCK,
            consumer_dt_path=IMR_PATH,
            provider_dt_path="/soc/clock-controller@e6150000",
        )

        report = InterruptCorrelationService().correlate(
            tree=_tree(),
            dependencies=(dependency,),
            interrupts=(),
        )

        self.assertEqual(report.correlations, ())
        self.assertEqual(report.warnings, ())

    def test_interrupt_correlation_model_validates_contract(self) -> None:
        dependency = _interrupt_dependency(specifier_cells=(0, 150, 4))
        identity = InterruptIdentity(
            controller_key="gic",
            hardware_irq=150,
            source="devicetree",
            source_path="/soc/imr@e6260000/interrupts",
        )
        warning = InterruptCorrelationWarning(
            code="TEST",
            message="test warning",
            consumer_dt_path=IMR_PATH,
        )
        correlation = InterruptCorrelation(
            dependency=dependency,
            dt_identities=[identity],
            resolution="resolved",
            match_method="controller_hardware_irq",
            warnings=[warning],
        )
        report = InterruptCorrelationReport(
            correlations=[correlation],
            warnings=[warning],
        )

        self.assertEqual(correlation.dt_identities, (identity,))
        self.assertEqual(correlation.resolution, InterruptCorrelationResolution.RESOLVED)
        self.assertEqual(report.correlations, (correlation,))

        with self.assertRaises(FrozenInstanceError):
            correlation.resolution = InterruptCorrelationResolution.UNRESOLVED

        with self.assertRaisesRegex(ValueError, "hardware_irq must be >= 0"):
            InterruptIdentity(controller_key="gic", hardware_irq=-1)

        with self.assertRaisesRegex(ValueError, "consumer_dt_path must be absolute"):
            InterruptCorrelationWarning(
                code="BAD",
                message="bad path",
                consumer_dt_path="soc/imr",
            )


def _tree(
    *,
    gic_interrupt_cells: int = 3,
    with_second_gic: bool = False,
) -> DeviceTree:
    gic = DeviceTreeNode(
        name="interrupt-controller",
        path=GIC_PATH,
        unit_address="f1000000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(name="interrupt-controller", raw_bytes=b""),
            strings("compatible", "arm,gic-v3"),
            cells("#interrupt-cells", gic_interrupt_cells),
            cells("phandle", 1),
        ),
    )
    second_gic = DeviceTreeNode(
        name="interrupt-controller",
        path=SECOND_GIC_PATH,
        unit_address="f2000000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(name="interrupt-controller", raw_bytes=b""),
            strings("compatible", "arm,gic-v3"),
            cells("#interrupt-cells", 3),
            cells("phandle", 2),
        ),
    )
    gpio = DeviceTreeNode(
        name="gpio",
        path=GPIO_PATH,
        unit_address="e6050000",
        parent_path="/soc",
        properties=(
            DeviceTreeProperty(name="interrupt-controller", raw_bytes=b""),
            strings("compatible", "renesas,gpio-r8a779g0"),
            cells("#interrupt-cells", 2),
        ),
    )
    imr = DeviceTreeNode(
        name="imr",
        path=IMR_PATH,
        unit_address="e6260000",
        parent_path="/soc",
    )
    soc_children = (
        (gic, second_gic, gpio, imr)
        if with_second_gic
        else (gic, gpio, imr)
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        children=soc_children,
    )
    root = DeviceTreeNode(name="/", path="/", children=(soc,))
    return DeviceTree(root=root)


def _interrupt_dependency(
    *,
    provider_dt_path: str | None = GIC_PATH,
    name: str | None = None,
    specifier_cells: tuple[int, ...],
    resolution: DependencyResolution = DependencyResolution.RESOLVED,
    message: str | None = None,
) -> DependencyReference:
    return DependencyReference(
        kind=DependencyKind.INTERRUPT,
        consumer_dt_path=IMR_PATH,
        provider_dt_path=provider_dt_path,
        provider_phandle=1 if provider_dt_path is not None else None,
        name=name,
        specifier_cells=specifier_cells,
        source_property="interrupts",
        resolution=resolution,
        evidence=(
            DependencyEvidence(
                kind=DependencyEvidenceKind.DECLARED,
                source="devicetree",
                source_path="/soc/imr@e6260000/interrupts",
                message=message,
            ),
        ),
    )


def _metadata(identity: InterruptIdentity, key: str) -> str | int | bool | None:
    for item_key, value in identity.metadata:
        if item_key == key:
            return value
    return None


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
    value: str | tuple[str, ...] = values[0] if len(values) == 1 else values
    return DeviceTreeProperty(
        name=name,
        raw_bytes=raw,
        kind=PropertyKind.STRING_LIST,
        value=value,
    )


if __name__ == "__main__":
    unittest.main()
