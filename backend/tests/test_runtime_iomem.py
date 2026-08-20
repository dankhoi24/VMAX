from __future__ import annotations

import unittest

from app.runtime import IomemRegion, parse_proc_iomem_file


class RuntimeIomemTest(unittest.TestCase):
    def test_parse_proc_iomem_file_parses_flat_regions(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-3fffffff : System RAM",
                    "fe201000-fe201fff : serial@7e201000",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 2)
        self.assertEqual(
            tuple(region.name for region in result.data),
            ("System RAM", "serial@7e201000"),
        )
        self.assertEqual(result.data[0].size, 0x40000000)
        self.assertEqual(result.data[1].start, 0xFE201000)

    def test_parse_proc_iomem_file_preserves_parent_child_hierarchy(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-3fffffff : System RAM",
                    "  00080000-00ffffff : Kernel code",
                    "  01000000-01ffffff : Kernel data",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)

        parent = result.data[0]
        self.assertIsInstance(parent, IomemRegion)
        self.assertEqual(parent.name, "System RAM")
        self.assertEqual(
            tuple(child.name for child in parent.children),
            ("Kernel code", "Kernel data"),
        )

    def test_parse_proc_iomem_file_supports_multiple_nesting_levels(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-3fffffff : System RAM",
                    "  00080000-00ffffff : Kernel image",
                    "    00080000-001fffff : Kernel code",
                    "    00200000-002fffff : Kernel data",
                )
            )
        )

        kernel_image = result.data[0].children[0]

        self.assertEqual(result.warnings, ())
        self.assertEqual(kernel_image.name, "Kernel image")
        self.assertEqual(
            tuple(child.name for child in kernel_image.children),
            ("Kernel code", "Kernel data"),
        )

    def test_parse_proc_iomem_file_uses_actual_indent_width(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-3fffffff : System RAM",
                    "    00080000-00ffffff : Kernel image",
                    "  01000000-01ffffff : Kernel data",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            tuple(child.name for child in result.data[0].children),
            ("Kernel image", "Kernel data"),
        )

    def test_parse_proc_iomem_file_preserves_multiple_root_regions(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-00000fff : reserved",
                    "00001000-3fffffff : System RAM",
                    "500000000-50000ffff : high-mmio",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            tuple(region.name for region in result.data),
            ("reserved", "System RAM", "high-mmio"),
        )
        self.assertEqual(result.data[2].start, 0x500000000)
        self.assertEqual(result.data[2].size, 0x10000)

    def test_parse_proc_iomem_file_reports_malformed_rows(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "",
                    "not-an-address : broken",
                    "00001000-00000fff : backwards",
                    "00002000-00002fff : valid",
                )
            ),
            "/proc/iomem",
        )

        self.assertEqual(tuple(region.name for region in result.data), ("valid",))
        self.assertEqual(len(result.warnings), 2)
        self.assertEqual(
            tuple(warning.code for warning in result.warnings),
            ("PROC_IOMEM_PARSE_FAILED", "PROC_IOMEM_PARSE_FAILED"),
        )
        self.assertEqual(
            tuple(warning.source_path for warning in result.warnings),
            ("/proc/iomem", "/proc/iomem"),
        )

    def test_parse_proc_iomem_file_skips_child_outside_parent(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00001000-00001fff : parent",
                    "  00003000-00003fff : invalid child",
                    "  00001800-00001fff : valid child",
                )
            )
        )

        self.assertEqual(
            tuple(child.name for child in result.data[0].children),
            ("valid child",),
        )
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_IOMEM_PARSE_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/iomem")

    def test_parse_proc_iomem_file_reports_redacted_addresses(self) -> None:
        result = parse_proc_iomem_file(
            "\n".join(
                (
                    "00000000-00000000 : System RAM",
                    "  00000000-00000000 : Kernel code",
                    "00000000-00000000 : Reserved",
                )
            ),
            "/proc/iomem",
        )

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "PROC_IOMEM_ADDRESSES_REDACTED",
        )
        self.assertEqual(result.warnings[0].source_path, "/proc/iomem")

    def test_parse_proc_iomem_file_keeps_single_zero_range(self) -> None:
        result = parse_proc_iomem_file("00000000-00000000 : single-byte-region")

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].start, 0)
        self.assertEqual(result.data[0].end, 0)
        self.assertEqual(result.data[0].size, 1)
