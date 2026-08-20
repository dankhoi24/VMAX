from __future__ import annotations

import unittest

from app.runtime import RuntimeResource, decode_resource_flag_names
from app.runtime.resources import parse_linux_resource_file


class RuntimeResourcesTest(unittest.TestCase):
    def test_parse_linux_resource_file_parses_one_mmio_resource(self) -> None:
        result = parse_linux_resource_file(
            "0x000000107d001000 0x000000107d0011ff 0x0000000000000200\n",
            "/sys/bus/pci/devices/0000:00:00.0/resource",
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)

        resource = result.data[0]
        self.assertIsInstance(resource, RuntimeResource)
        self.assertEqual(resource.index, 0)
        self.assertEqual(resource.start, 0x107D001000)
        self.assertEqual(resource.end, 0x107D0011FF)
        self.assertEqual(resource.size, 0x200)
        self.assertEqual(resource.flags, 0x200)
        self.assertEqual(resource.flag_names, ("MEM",))

    def test_parse_linux_resource_file_preserves_multiple_row_indices(self) -> None:
        result = parse_linux_resource_file(
            "\n".join(
                (
                    "0x0000000000001000 0x0000000000001fff 0x0000000000000200",
                    "0x0000000000000020 0x000000000000002f 0x0000000000000100",
                )
            ),
            "/sys/bus/pci/devices/0000:00:00.0/resource",
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(tuple(resource.index for resource in result.data), (0, 1))
        self.assertEqual(
            tuple(resource.flag_names for resource in result.data),
            (
                ("MEM",),
                ("IO",),
            ),
        )

    def test_parse_linux_resource_file_reports_malformed_rows(self) -> None:
        result = parse_linux_resource_file(
            "\n".join(
                (
                    "bad line",
                    "0x0000000000001000 0x0000000000001fff 0x0000000000000200",
                    "0x0000000000003000 0x0000000000002000 0x0000000000000200",
                )
            ),
            "/sys/bus/pci/devices/0000:00:00.0/resource",
        )

        self.assertEqual(tuple(resource.index for resource in result.data), (1,))
        self.assertEqual(len(result.warnings), 2)
        self.assertEqual(
            tuple(warning.code for warning in result.warnings),
            (
                "LINUX_RESOURCE_PARSE_FAILED",
                "LINUX_RESOURCE_PARSE_FAILED",
            ),
        )
        self.assertEqual(
            tuple(warning.source_path for warning in result.warnings),
            (
                "/sys/bus/pci/devices/0000:00:00.0/resource",
                "/sys/bus/pci/devices/0000:00:00.0/resource",
            ),
        )

    def test_parse_linux_resource_file_skips_empty_resource_slots(self) -> None:
        result = parse_linux_resource_file(
            "\n".join(
                (
                    "0x0000000000000000 0x0000000000000000 0x0000000000000000",
                    "0x00000000f0000000 0x00000000f00fffff 0x0000000000000200",
                    "0x0000000000000000 0x0000000000000000 0x0000000000000000",
                )
            ),
            "/sys/bus/pci/devices/0000:00:00.0/resource",
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(tuple(resource.index for resource in result.data), (1,))
        self.assertEqual(result.data[0].start, 0xF0000000)
        self.assertEqual(result.data[0].end, 0xF00FFFFF)
        self.assertEqual(result.data[0].size, 0x100000)
        self.assertEqual(result.data[0].flag_names, ("MEM",))

    def test_decode_resource_flag_names_uses_resource_type_bits(self) -> None:
        self.assertEqual(decode_resource_flag_names(0x100), ("IO",))
        self.assertEqual(decode_resource_flag_names(0x200), ("MEM",))
        self.assertEqual(decode_resource_flag_names(0x300), ("REG",))
        self.assertEqual(decode_resource_flag_names(0x400), ("IRQ",))
        self.assertEqual(decode_resource_flag_names(0x800), ("DMA",))
        self.assertEqual(decode_resource_flag_names(0x1000), ("BUS",))
        self.assertEqual(decode_resource_flag_names(0x2200), ("MEM",))
        self.assertEqual(decode_resource_flag_names(0), ())
