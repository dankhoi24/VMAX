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
