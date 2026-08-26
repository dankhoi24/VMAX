from __future__ import annotations

import unittest

from app.runtime.interrupts import (
    PROC_INTERRUPTS_PARSE_FAILED,
    parse_interrupt_actions,
    parse_proc_interrupts_file,
)


class RuntimeInterruptsParserTest(unittest.TestCase):
    def test_parse_proc_interrupts_gic_line(self) -> None:
        result = parse_proc_interrupts_file(
            "\n".join(
                (
                    "           CPU0       CPU1       CPU2       CPU3",
                    "182:          0       4291          0          0  GICv3  150 Level imr",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        interrupt = result.data[0]
        self.assertEqual(interrupt.irq, 182)
        self.assertEqual(interrupt.counts, (0, 4291, 0, 0))
        self.assertEqual(interrupt.total_count, 4291)
        self.assertEqual(interrupt.controller, "GICv3")
        self.assertEqual(interrupt.hardware_irq, 150)
        self.assertEqual(interrupt.trigger, "Level")
        self.assertEqual(interrupt.actions, ("imr",))
        self.assertEqual(interrupt.source_path, "/proc/interrupts")
        self.assertIn("GICv3", interrupt.raw_line or "")
        self.assertIn(("primary_source", "/proc/interrupts"), interrupt.metadata)
        self.assertIn(("hardware_irq_source", "/proc/interrupts"), interrupt.metadata)

    def test_parse_proc_interrupts_skips_headers_and_non_linux_irq_rows(self) -> None:
        result = parse_proc_interrupts_file(
            "\n".join(
                (
                    "           CPU0       CPU1",
                    "IPI0:          1          2  Rescheduling interrupts",
                    "ERR:           0",
                    "210:         105          0  GICv3  178 Level isp",
                )
            )
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(tuple(interrupt.irq for interrupt in result.data), (210,))

    def test_cpu_header_defines_exact_count_columns(self) -> None:
        result = parse_proc_interrupts_file(
            "\n".join(
                (
                    "           CPU0       CPU1       CPU2       CPU3",
                    "182:          0       4291          0  GICv3  150 Level imr",
                    "210:        105          0          0          0  GICv3  178 Level isp",
                )
            )
        )

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].irq, 210)
        self.assertEqual(result.data[0].counts, (105, 0, 0, 0))
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, PROC_INTERRUPTS_PARSE_FAILED)
        self.assertIn("expected 4 CPU counters", result.warnings[0].message)

    def test_parse_proc_interrupts_reports_malformed_numeric_irq_row(self) -> None:
        result = parse_proc_interrupts_file(
            "182: GICv3 imr\n",
            source_path="/proc/interrupts",
        )

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, PROC_INTERRUPTS_PARSE_FAILED)
        self.assertEqual(result.warnings[0].source_path, "/proc/interrupts")

    def test_parse_proc_interrupts_preserves_format_specific_description(self) -> None:
        result = parse_proc_interrupts_file(
            "24: 0 0 IO-APIC 2-edge timer\n",
            source_path="/proc/interrupts",
        )

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        interrupt = result.data[0]
        self.assertEqual(interrupt.controller, "IO-APIC")
        self.assertIsNone(interrupt.hardware_irq)
        self.assertIsNone(interrupt.trigger)
        self.assertEqual(interrupt.actions, ("2-edge timer",))
        self.assertEqual(interrupt.raw_line, "24: 0 0 IO-APIC 2-edge timer")

    def test_parse_interrupt_actions_splits_comma_separated_sysfs_actions(self) -> None:
        self.assertEqual(parse_interrupt_actions("imr, isp\n"), ("imr", "isp"))
        self.assertEqual(parse_interrupt_actions("arch_timer"), ("arch_timer",))
        self.assertEqual(parse_interrupt_actions(""), ())


if __name__ == "__main__":
    unittest.main()
