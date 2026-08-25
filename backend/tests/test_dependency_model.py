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


class DependencyModelTest(unittest.TestCase):
    def test_dependency_kind_covers_v0_5_dependency_types(self) -> None:
        self.assertEqual(
            {kind.value for kind in DependencyKind},
            {
                "interrupt",
                "clock",
                "reset",
                "power_domain",
                "dma",
                "iommu",
            },
        )

    def test_dependency_evidence_kind_distinguishes_evidence_semantics(self) -> None:
        self.assertEqual(
            {kind.value for kind in DependencyEvidenceKind},
            {
                "declared",
                "observed",
                "inferred",
            },
        )

    def test_dependency_resolution_distinguishes_resolution_semantics(self) -> None:
        self.assertEqual(
            {resolution.value for resolution in DependencyResolution},
            {
                "resolved",
                "unresolved",
                "unavailable",
                "ambiguous",
            },
        )

    def test_declared_clock_reference_preserves_dt_provenance(self) -> None:
        reference = DependencyReference(
            kind=DependencyKind.CLOCK,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path="/soc/clock-controller@e6150000",
            entry_index=1,
            provider_phandle=0x17,
            name="cnn",
            specifier_cells=[12, 4],
            source_property="clocks",
        )

        self.assertEqual(reference.kind, DependencyKind.CLOCK)
        self.assertEqual(reference.consumer_dt_path, "/soc/cnn@e2200000")
        self.assertEqual(
            reference.provider_dt_path,
            "/soc/clock-controller@e6150000",
        )
        self.assertEqual(reference.entry_index, 1)
        self.assertEqual(reference.provider_phandle, 0x17)
        self.assertEqual(reference.name, "cnn")
        self.assertEqual(reference.specifier_cells, (12, 4))
        self.assertEqual(reference.source_property, "clocks")
        self.assertEqual(reference.resolution, DependencyResolution.RESOLVED)
        self.assertEqual(reference.evidence, ())

    def test_reference_accepts_string_enums_and_iommu_specifier(self) -> None:
        reference = DependencyReference(
            kind="iommu",
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path="/soc/iommu@e6740000",
            specifier_cells=(3,),
            source_property="iommus",
            resolution="resolved",
        )

        self.assertEqual(reference.kind, DependencyKind.IOMMU)
        self.assertEqual(reference.resolution, DependencyResolution.RESOLVED)
        self.assertEqual(reference.specifier_cells, (3,))

    def test_evidence_preserves_source_path_and_kind(self) -> None:
        evidence = DependencyEvidence(
            kind="observed",
            source="proc_interrupts",
            source_path="/proc/interrupts",
            message="Linux observed interrupt action cnn",
        )
        reference = DependencyReference(
            kind=DependencyKind.INTERRUPT,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path="/interrupt-controller@f1000000",
            specifier_cells=(0, 150, 4),
            source_property="interrupts",
            resolution=DependencyResolution.RESOLVED,
            evidence=[evidence],
        )

        self.assertEqual(evidence.kind, DependencyEvidenceKind.OBSERVED)
        self.assertEqual(reference.evidence, (evidence,))
        self.assertEqual(reference.resolution, DependencyResolution.RESOLVED)

    def test_reference_supports_unavailable_and_ambiguous_resolution(self) -> None:
        unavailable = DependencyReference(
            kind=DependencyKind.RESET,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path=None,
            provider_phandle=0x35,
            source_property="resets",
            resolution=DependencyResolution.UNAVAILABLE,
            evidence=[
                DependencyEvidence(
                    kind=DependencyEvidenceKind.DECLARED,
                    source="devicetree",
                    message="Reset provider phandle could not be resolved",
                )
            ],
        )
        ambiguous = DependencyReference(
            kind=DependencyKind.DMA,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path=None,
            source_property="dmas",
            resolution=DependencyResolution.AMBIGUOUS,
        )

        self.assertIsNone(unavailable.provider_dt_path)
        self.assertEqual(unavailable.provider_phandle, 0x35)
        self.assertEqual(unavailable.resolution, DependencyResolution.UNAVAILABLE)
        self.assertEqual(ambiguous.resolution, DependencyResolution.AMBIGUOUS)

    def test_reference_preserves_unresolved_phandle(self) -> None:
        reference = DependencyReference(
            kind=DependencyKind.IOMMU,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path=None,
            provider_phandle=0x35,
            entry_index=0,
            specifier_cells=(3,),
            source_property="iommus",
            resolution=DependencyResolution.UNRESOLVED,
            evidence=(
                DependencyEvidence(
                    kind=DependencyEvidenceKind.DECLARED,
                    source="devicetree",
                    source_path="/soc/cnn@e2200000/iommus",
                ),
            ),
        )

        self.assertIsNone(reference.provider_dt_path)
        self.assertEqual(reference.provider_phandle, 0x35)
        self.assertEqual(reference.specifier_cells, (3,))
        self.assertEqual(reference.resolution, DependencyResolution.UNRESOLVED)

    def test_resolved_reference_requires_provider_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider_dt_path is required"):
            DependencyReference(
                kind=DependencyKind.IOMMU,
                consumer_dt_path="/soc/cnn@e2200000",
                provider_dt_path=None,
                provider_phandle=0x35,
                resolution=DependencyResolution.RESOLVED,
            )

    def test_collections_are_immutable_tuples(self) -> None:
        evidence = DependencyEvidence(
            kind=DependencyEvidenceKind.DECLARED,
            source="devicetree",
            source_path="/soc/cnn@e2200000/clocks",
        )
        reference = DependencyReference(
            kind=DependencyKind.POWER_DOMAIN,
            consumer_dt_path="/soc/cnn@e2200000",
            provider_dt_path="/sysc/power-domain@0",
            specifier_cells=[0],
            evidence=[evidence],
        )

        self.assertEqual(reference.specifier_cells, (0,))
        self.assertEqual(reference.evidence, (evidence,))
        with self.assertRaises(FrozenInstanceError):
            reference.resolution = DependencyResolution.UNAVAILABLE

    def test_invalid_paths_names_and_sources_fail_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "consumer_dt_path must be absolute"):
            DependencyReference(
                kind=DependencyKind.CLOCK,
                consumer_dt_path="soc/cnn@e2200000",
                provider_dt_path="/soc/clock-controller@e6150000",
            )

        with self.assertRaisesRegex(ValueError, "provider_dt_path must be absolute"):
            DependencyReference(
                kind=DependencyKind.CLOCK,
                consumer_dt_path="/soc/cnn@e2200000",
                provider_dt_path="soc/clock-controller@e6150000",
            )

        with self.assertRaisesRegex(ValueError, "name must not be empty"):
            DependencyReference(
                kind=DependencyKind.CLOCK,
                consumer_dt_path="/soc/cnn@e2200000",
                provider_dt_path=None,
                name="",
            )

        with self.assertRaisesRegex(ValueError, "source_property must not be empty"):
            DependencyReference(
                kind=DependencyKind.CLOCK,
                consumer_dt_path="/soc/cnn@e2200000",
                provider_dt_path=None,
                source_property="",
            )

        with self.assertRaisesRegex(ValueError, "source must not be empty"):
            DependencyEvidence(kind=DependencyEvidenceKind.DECLARED, source="")

        with self.assertRaisesRegex(ValueError, "source_path must be absolute"):
            DependencyEvidence(
                kind=DependencyEvidenceKind.DECLARED,
                source="devicetree",
                source_path="soc/cnn@e2200000",
            )

    def test_entry_index_rejects_invalid_values(self) -> None:
        for bad_index, expected_error in (
            (-1, ValueError),
            (True, TypeError),
            (1.5, TypeError),
        ):
            with self.subTest(bad_index=bad_index):
                with self.assertRaises(expected_error):
                    DependencyReference(
                        kind=DependencyKind.CLOCK,
                        consumer_dt_path="/soc/cnn@e2200000",
                        provider_dt_path="/soc/clock-controller@e6150000",
                        entry_index=bad_index,
                    )

    def test_specifier_cells_and_provider_phandle_reject_invalid_values(self) -> None:
        for bad_cell, expected_error in (
            (-1, ValueError),
            (0x1_0000_0000, ValueError),
            (True, TypeError),
            (1.5, TypeError),
        ):
            with self.subTest(bad_cell=bad_cell):
                with self.assertRaises(expected_error):
                    DependencyReference(
                        kind=DependencyKind.INTERRUPT,
                        consumer_dt_path="/soc/cnn@e2200000",
                        provider_dt_path="/interrupt-controller@f1000000",
                        specifier_cells=(bad_cell,),
                    )

        for bad_phandle, expected_error in (
            (-1, ValueError),
            (0x1_0000_0000, ValueError),
            (True, TypeError),
            (1.5, TypeError),
        ):
            with self.subTest(bad_phandle=bad_phandle):
                with self.assertRaises(expected_error):
                    DependencyReference(
                        kind=DependencyKind.IOMMU,
                        consumer_dt_path="/soc/cnn@e2200000",
                        provider_dt_path=None,
                        provider_phandle=bad_phandle,
                        resolution=DependencyResolution.UNRESOLVED,
                    )

    def test_evidence_tuple_rejects_non_evidence_items(self) -> None:
        with self.assertRaisesRegex(TypeError, "evidence must be DependencyEvidence"):
            DependencyReference(
                kind=DependencyKind.CLOCK,
                consumer_dt_path="/soc/cnn@e2200000",
                provider_dt_path="/soc/clock-controller@e6150000",
                evidence=("not evidence",),
            )


if __name__ == "__main__":
    unittest.main()
