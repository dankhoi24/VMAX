from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from app.runtime import (
    LocalLinuxRuntimeProvider,
    RuntimeCollection,
    RuntimeProvider,
    RuntimeSystemInfo,
)


class LocalLinuxRuntimeProviderTest(unittest.TestCase):
    def test_default_roots_point_to_linux_runtime_filesystems(self) -> None:
        provider = LocalLinuxRuntimeProvider()

        self.assertEqual(provider.sysfs_root, Path("/sys"))
        self.assertEqual(provider.proc_root, Path("/proc"))

    def test_custom_roots_are_stored_for_fixture_based_collection(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            sysfs_root = fixture_root / "sys"
            proc_root = fixture_root / "proc"
            sysfs_root.mkdir()
            proc_root.mkdir()

            provider = LocalLinuxRuntimeProvider(
                sysfs_root=sysfs_root,
                proc_root=proc_root,
            )

            self.assertEqual(provider.sysfs_root, sysfs_root)
            self.assertEqual(provider.proc_root, proc_root)

    def test_collect_system_info_maps_uname_hostname_and_cmdline(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            proc_root = fixture_root / "proc"
            proc_root.mkdir()
            (proc_root / "cmdline").write_text(
                "console=ttyAMA10 root=/dev/mmcblk0p2\n",
                encoding="utf-8",
            )
            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)

            with _patched_runtime(machine="aarch64"):
                result = provider.collect_system_info()

        self.assertEqual(result.data.hostname, "pi5")
        self.assertEqual(result.data.kernel_name, "Linux")
        self.assertEqual(result.data.kernel_release, "6.12.80-v8")
        self.assertEqual(result.data.kernel_version, "#1 SMP PREEMPT")
        self.assertEqual(result.data.machine, "aarch64")
        self.assertEqual(result.data.architecture, "arm64")
        self.assertEqual(
            result.data.cmdline,
            "console=ttyAMA10 root=/dev/mmcblk0p2",
        )
        self.assertEqual(result.warnings, ())

    def test_collect_system_info_normalizes_known_architectures(self) -> None:
        cases = (
            ("aarch64", "arm64"),
            ("arm64", "arm64"),
            ("x86_64", "x86_64"),
            ("amd64", "x86_64"),
            ("riscv64", "riscv64"),
            ("mips64", "mips64"),
        )

        with tempfile.TemporaryDirectory() as root:
            proc_root = Path(root) / "proc"
            proc_root.mkdir()
            (proc_root / "cmdline").write_text("", encoding="utf-8")
            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)

            for machine, expected in cases:
                with self.subTest(machine=machine), _patched_runtime(machine=machine):
                    result = provider.collect_system_info()

                self.assertEqual(result.data.machine, machine)
                self.assertEqual(result.data.architecture, expected)

    def test_collect_system_info_reports_missing_cmdline_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            provider = LocalLinuxRuntimeProvider(proc_root=Path(root) / "proc")

            with _patched_runtime(machine="x86_64"):
                result = provider.collect_system_info()

        self.assertEqual(result.data.hostname, "pi5")
        self.assertEqual(result.data.machine, "x86_64")
        self.assertEqual(result.data.architecture, "x86_64")
        self.assertIsNone(result.data.cmdline)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_CMDLINE_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/cmdline")
        self.assertNotIn(str(Path(root)), result.warnings[0].message)

    def test_collect_system_info_reports_cmdline_read_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(proc_root=Path("/fixture/proc"))

        with _patched_runtime(machine="riscv64"):
            with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                result = provider.collect_system_info()

        self.assertEqual(result.data.architecture, "riscv64")
        self.assertIsNone(result.data.cmdline)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_CMDLINE_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/cmdline")

    def test_collect_system_info_reports_cmdline_decode_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(proc_root=Path("/fixture/proc"))
        decode_error = UnicodeDecodeError(
            "utf-8",
            b"\xff",
            0,
            1,
            "invalid start byte",
        )

        with _patched_runtime(machine="aarch64"):
            with patch.object(Path, "read_text", side_effect=decode_error):
                result = provider.collect_system_info()

        self.assertEqual(result.data.architecture, "arm64")
        self.assertIsNone(result.data.cmdline)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_CMDLINE_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/cmdline")

    def test_collect_system_info_reports_uname_failure_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            proc_root = Path(root) / "proc"
            proc_root.mkdir()
            (proc_root / "cmdline").write_text("quiet\n", encoding="utf-8")
            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)

            with patch(
                "app.runtime.local_linux.os.uname",
                side_effect=OSError("uname failed"),
                create=True,
            ):
                with patch(
                    "app.runtime.local_linux.socket.gethostname",
                    return_value="pi5",
                ):
                    result = provider.collect_system_info()

        self.assertEqual(result.data.hostname, "pi5")
        self.assertIsNone(result.data.kernel_name)
        self.assertIsNone(result.data.machine)
        self.assertIsNone(result.data.architecture)
        self.assertEqual(result.data.cmdline, "quiet")
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "UNAME_READ_FAILED")

    def test_collect_system_info_reports_hostname_failure_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            proc_root = Path(root) / "proc"
            proc_root.mkdir()
            (proc_root / "cmdline").write_text("quiet\n", encoding="utf-8")
            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)

            with _patched_runtime(machine="aarch64"):
                with patch(
                    "app.runtime.local_linux.socket.gethostname",
                    side_effect=OSError("hostname failed"),
                ):
                    result = provider.collect_system_info()

        self.assertIsNone(result.data.hostname)
        self.assertEqual(result.data.kernel_name, "Linux")
        self.assertEqual(result.data.machine, "aarch64")
        self.assertEqual(result.data.architecture, "arm64")
        self.assertEqual(result.data.cmdline, "quiet")
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "HOSTNAME_READ_FAILED")

    def test_fixture_roots_change_access_paths_not_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            provider = LocalLinuxRuntimeProvider(
                sysfs_root=fixture_root / "sys",
                proc_root=fixture_root / "proc",
            )

            self.assertEqual(
                provider._sysfs_access_path("bus/platform/devices/foo"),
                fixture_root / "sys" / "bus/platform/devices/foo",
            )
            self.assertEqual(
                provider._proc_access_path("iomem"),
                fixture_root / "proc" / "iomem",
            )
            self.assertEqual(
                provider._sysfs_runtime_path("bus/platform/devices/foo"),
                "/sys/bus/platform/devices/foo",
            )
            self.assertEqual(
                provider._proc_runtime_path("iomem"),
                "/proc/iomem",
            )

    def test_helper_relative_paths_must_not_be_empty_or_absolute(self) -> None:
        provider = LocalLinuxRuntimeProvider()

        with self.assertRaisesRegex(ValueError, "relative_path must not be empty"):
            provider._sysfs_access_path("")

        with self.assertRaisesRegex(ValueError, "relative_path must be relative"):
            provider._proc_runtime_path("/iomem")

    def test_rejects_empty_root_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "sysfs_root must not be empty"):
            LocalLinuxRuntimeProvider(sysfs_root="")

        with self.assertRaisesRegex(ValueError, "proc_root must not be empty"):
            LocalLinuxRuntimeProvider(proc_root="")

    def test_provider_satisfies_runtime_provider_contract(self) -> None:
        provider: RuntimeProvider = LocalLinuxRuntimeProvider()

        system_info = provider.collect_system_info()
        devices = provider.collect_devices()
        drivers = provider.collect_drivers()
        iomem = provider.collect_iomem()

        self.assertIsInstance(system_info, RuntimeCollection)
        self.assertIsInstance(system_info.data, RuntimeSystemInfo)
        self.assertEqual(devices.data, ())
        self.assertEqual(devices.warnings, ())
        self.assertEqual(drivers.data, ())
        self.assertEqual(drivers.warnings, ())
        self.assertEqual(iomem.data, ())
        self.assertEqual(iomem.warnings, ())


def _patched_runtime(machine: str):
    uname = SimpleNamespace(
        sysname="Linux",
        release="6.12.80-v8",
        version="#1 SMP PREEMPT",
        machine=machine,
    )
    return _PatchedRuntime(uname)


class _PatchedRuntime:
    def __init__(self, uname: SimpleNamespace) -> None:
        self._uname = uname
        self._patches = (
            patch(
                "app.runtime.local_linux.os.uname",
                return_value=uname,
                create=True,
            ),
            patch(
                "app.runtime.local_linux.socket.gethostname",
                return_value="pi5",
            ),
        )

    def __enter__(self) -> "_PatchedRuntime":
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *args: object) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()
