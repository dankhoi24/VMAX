from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from app.dependency import (
    DependencyEvidence,
    DependencyEvidenceKind,
    DependencyKind,
    DependencyReference,
    DependencyResolution,
    DependencyViewBuilder,
    DependencyViewReport,
    DependencyViewWarning,
    DeviceDependency,
    DeviceDependencyView,
)
from app.interrupts import (
    InterruptCorrelation,
    InterruptCorrelationResolution,
    InterruptCorrelationWarning,
)
from app.runtime import RuntimeInterrupt


CNN_PATH = "/soc/cnn@e2200000"
IMR_PATH = "/soc/imr@e6260000"
CPG_PATH = "/soc/clock-controller@e6150000"
GIC_PATH = "/soc/interrupt-controller@f1000000"
IPMMU_PATH = "/soc/iommu@e6740000"


class DependencyCoreTest(unittest.TestCase):
    def test_builds_device_centric_views_with_stable_dependency_order(self) -> None:
        reset = _reference(
            kind=DependencyKind.RESET,
            consumer_dt_path=CNN_PATH,
            provider_dt_path=CPG_PATH,
            source_property="resets",
            specifier_cells=(31,),
        )
        clock = _reference(
            kind=DependencyKind.CLOCK,
            consumer_dt_path=CNN_PATH,
            provider_dt_path=CPG_PATH,
            source_property="clocks",
            specifier_cells=(12, 4),
        )
        interrupt = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        iommu = _reference(
            kind=DependencyKind.IOMMU,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=IPMMU_PATH,
            source_property="iommus",
            specifier_cells=(3,),
        )

        report = DependencyViewBuilder().build(
            dependencies=(interrupt, reset, iommu, clock),
        )

        self.assertEqual(
            tuple(view.dt_node_path for view in report.devices),
            (CNN_PATH, IMR_PATH),
        )
        self.assertEqual(
            tuple(dependency.kind for dependency in report.devices[0].dependencies),
            (DependencyKind.CLOCK, DependencyKind.RESET),
        )
        self.assertEqual(
            tuple(dependency.kind for dependency in report.devices[1].dependencies),
            (DependencyKind.IOMMU, DependencyKind.INTERRUPT),
        )
        self.assertEqual(
            report.devices[0].dependencies_by_kind("clock"),
            (report.devices[0].dependencies[0],),
        )
        self.assertEqual(report.warnings, ())

    def test_attaches_interrupt_correlation_to_matching_dependency(self) -> None:
        dependency = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        runtime_irq = RuntimeInterrupt(
            irq=214,
            counts=(0, 4, 0, 0),
            controller="GICv3",
            hardware_irq=182,
        )
        warning = InterruptCorrelationWarning(
            code="TRACE",
            message="trace warning",
            consumer_dt_path=IMR_PATH,
        )
        correlation = InterruptCorrelation(
            dependency=dependency,
            runtime_interrupt=runtime_irq,
            runtime_candidates=(runtime_irq,),
            resolution=InterruptCorrelationResolution.RESOLVED,
            warnings=(warning,),
        )

        report = DependencyViewBuilder().build(
            dependencies=(dependency,),
            interrupt_correlations=(correlation,),
        )

        (device,) = report.devices
        (device_dependency,) = device.dependencies
        self.assertIs(device_dependency.static_reference, dependency)
        self.assertIs(device_dependency.interrupt_correlation, correlation)
        self.assertIs(device_dependency.runtime_interrupt, runtime_irq)
        self.assertEqual(
            device_dependency.interrupt_resolution,
            InterruptCorrelationResolution.RESOLVED,
        )
        self.assertEqual(device_dependency.interrupt_warnings, (warning,))
        self.assertEqual(device_dependency.resolution, DependencyResolution.RESOLVED)

    def test_non_interrupt_dependency_cannot_hold_interrupt_correlation(self) -> None:
        clock = _reference(
            kind=DependencyKind.CLOCK,
            consumer_dt_path=CNN_PATH,
            provider_dt_path=CPG_PATH,
            source_property="clocks",
        )
        interrupt = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        correlation = InterruptCorrelation(dependency=interrupt)

        with self.assertRaisesRegex(ValueError, "requires an interrupt dependency"):
            DeviceDependency(
                static_reference=clock,
                interrupt_correlation=correlation,
            )

    def test_mismatched_interrupt_correlation_is_rejected(self) -> None:
        interrupt_a = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        interrupt_b = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            entry_index=1,
            source_property="interrupts",
            specifier_cells=(0, 151, 4),
        )
        correlation = InterruptCorrelation(dependency=interrupt_b)

        with self.assertRaisesRegex(ValueError, "same dependency reference"):
            DeviceDependency(
                static_reference=interrupt_a,
                interrupt_correlation=correlation,
            )

    def test_orphan_interrupt_correlation_becomes_report_warning(self) -> None:
        dependency = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        correlation = InterruptCorrelation(dependency=dependency)

        report = DependencyViewBuilder().build(
            dependencies=(),
            interrupt_correlations=(correlation,),
        )

        self.assertEqual(report.devices, ())
        self.assertEqual(len(report.warnings), 1)
        self.assertEqual(
            report.warnings[0].code,
            "INTERRUPT_CORRELATION_WITHOUT_DEPENDENCY",
        )
        self.assertEqual(report.warnings[0].consumer_dt_path, IMR_PATH)
        self.assertEqual(report.warnings[0].source_path, f"{IMR_PATH}/interrupts")

    def test_duplicate_interrupt_correlations_do_not_pick_one_silently(self) -> None:
        dependency = _reference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path=IMR_PATH,
            provider_dt_path=GIC_PATH,
            source_property="interrupts",
            specifier_cells=(0, 150, 4),
        )
        correlation = InterruptCorrelation(dependency=dependency)

        report = DependencyViewBuilder().build(
            dependencies=(dependency,),
            interrupt_correlations=(correlation, correlation),
        )

        (device_dependency,) = report.devices[0].dependencies
        self.assertIsNone(device_dependency.interrupt_correlation)
        self.assertEqual(len(report.warnings), 1)
        self.assertEqual(
            report.warnings[0].code,
            "INTERRUPT_CORRELATION_DUPLICATE_FOR_DEPENDENCY",
        )

    def test_core_models_are_immutable_and_validate_paths(self) -> None:
        dependency = _reference(
            kind=DependencyKind.CLOCK,
            consumer_dt_path=CNN_PATH,
            provider_dt_path=CPG_PATH,
            source_property="clocks",
        )
        device_dependency = DeviceDependency(static_reference=dependency)
        view = DeviceDependencyView(
            dt_node_path=CNN_PATH,
            dependencies=[device_dependency],
        )
        report = DependencyViewReport(devices=[view])

        self.assertEqual(view.dependencies, (device_dependency,))
        self.assertEqual(report.devices, (view,))
        self.assertEqual(report.dependencies, (device_dependency,))

        with self.assertRaises(FrozenInstanceError):
            view.dt_node_path = IMR_PATH

        with self.assertRaisesRegex(ValueError, "dt_node_path must be absolute"):
            DeviceDependencyView(dt_node_path="soc/cnn")

        with self.assertRaisesRegex(ValueError, "belong to dt_node_path"):
            DeviceDependencyView(
                dt_node_path=IMR_PATH,
                dependencies=(device_dependency,),
            )

        with self.assertRaisesRegex(ValueError, "source_path must be absolute"):
            DependencyViewWarning(
                code="BAD",
                message="bad source",
                source_path="soc/cnn",
            )


def _reference(
    *,
    kind: DependencyKind,
    consumer_dt_path: str,
    provider_dt_path: str | None,
    source_property: str,
    entry_index: int = 0,
    specifier_cells: tuple[int, ...] = (),
) -> DependencyReference:
    return DependencyReference(
        kind=kind,
        consumer_dt_path=consumer_dt_path,
        provider_dt_path=provider_dt_path,
        entry_index=entry_index,
        provider_phandle=1 if provider_dt_path is not None else None,
        specifier_cells=specifier_cells,
        source_property=source_property,
        resolution=(
            DependencyResolution.RESOLVED
            if provider_dt_path is not None
            else DependencyResolution.UNRESOLVED
        ),
        evidence=(
            DependencyEvidence(
                kind=DependencyEvidenceKind.DECLARED,
                source="devicetree",
                source_path=f"{consumer_dt_path}/{source_property}",
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
