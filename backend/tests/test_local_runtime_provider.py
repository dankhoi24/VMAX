from __future__ import annotations

import tempfile
import unittest
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
        self.assertEqual(system_info.warnings, ())
        self.assertEqual(devices.data, ())
        self.assertEqual(devices.warnings, ())
        self.assertEqual(drivers.data, ())
        self.assertEqual(drivers.warnings, ())
        self.assertEqual(iomem.data, ())
        self.assertEqual(iomem.warnings, ())
