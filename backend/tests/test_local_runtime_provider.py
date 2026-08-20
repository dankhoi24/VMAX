from __future__ import annotations

import errno
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from app.runtime import (
    IomemRegion,
    LocalLinuxRuntimeProvider,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
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

    def test_collect_devices_enumerates_platform_device_directories(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            (devices_root / "107d001000.serial").mkdir()
            (devices_root / "1000fff000.mmc").mkdir()
            (devices_root / "fixedregulator_3v3").mkdir()
            (devices_root / "README").write_text("not a device", encoding="utf-8")

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_devices()

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            tuple(device.name for device in result.data),
            (
                "1000fff000.mmc",
                "107d001000.serial",
                "fixedregulator_3v3",
            ),
        )
        self.assertEqual(
            tuple(device.sysfs_path for device in result.data),
            (
                "/sys/bus/platform/devices/1000fff000.mmc",
                "/sys/bus/platform/devices/107d001000.serial",
                "/sys/bus/platform/devices/fixedregulator_3v3",
            ),
        )
        for device in result.data:
            self.assertEqual(device.bus, "platform")
            self.assertIsNone(device.driver_name)
            self.assertIsNone(device.driver_path)
            self.assertIsNone(device.of_node_sysfs_path)
            self.assertEqual(device.resources, ())
            self.assertNotIn(str(fixture_root), device.sysfs_path)

    def test_collect_devices_populates_bound_platform_driver(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            drivers_root = fixture_root / "sys" / "bus" / "platform" / "drivers"
            drivers_root.mkdir(parents=True)
            device = devices_root / "107d001000.serial"
            device.mkdir()
            driver_target = drivers_root / "serial8250"
            driver_target.mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks({device / "driver": driver_target}):
                result = provider.collect_devices()

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].driver_name, "serial8250")
        self.assertEqual(
            result.data[0].driver_path,
            "/sys/bus/platform/drivers/serial8250",
        )
        self.assertNotIn(str(fixture_root), result.data[0].driver_path or "")

    def test_collect_devices_treats_missing_driver_symlink_as_unbound(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            (devices_root / "unbound-device").mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "unbound-device")
        self.assertIsNone(result.data[0].driver_name)
        self.assertIsNone(result.data[0].driver_path)
        self.assertEqual(result.warnings, ())

    def test_collect_devices_reports_broken_driver_symlink_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            device = devices_root / "broken-driver-device"
            device.mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {device / "driver": fixture_root / "sys" / "broken-driver"},
                resolve_errors={
                    device / "driver": FileNotFoundError("broken symlink"),
                },
            ):
                result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "broken-driver-device")
        self.assertIsNone(result.data[0].driver_name)
        self.assertIsNone(result.data[0].driver_path)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices/broken-driver-device/driver",
        )
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

    def test_collect_devices_reports_driver_readlink_error_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            device = devices_root / "secret-driver-device"
            device.mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {device / "driver": PermissionError("denied")}
            ):
                result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "secret-driver-device")
        self.assertIsNone(result.data[0].driver_name)
        self.assertIsNone(result.data[0].driver_path)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices/secret-driver-device/driver",
        )

    def test_collect_devices_supports_bound_and_unbound_devices_together(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            drivers_root = fixture_root / "sys" / "bus" / "platform" / "drivers"
            drivers_root.mkdir(parents=True)
            bound = devices_root / "107d001000.serial"
            unbound = devices_root / "1000fff000.mmc"
            bound.mkdir()
            unbound.mkdir()
            driver_target = drivers_root / "serial8250"
            driver_target.mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks({bound / "driver": driver_target}):
                result = provider.collect_devices()

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            tuple(device.name for device in result.data),
            ("1000fff000.mmc", "107d001000.serial"),
        )
        self.assertIsNone(result.data[0].driver_name)
        self.assertIsNone(result.data[0].driver_path)
        self.assertEqual(result.data[1].driver_name, "serial8250")
        self.assertEqual(
            result.data[1].driver_path,
            "/sys/bus/platform/drivers/serial8250",
        )

    def test_collect_devices_returns_empty_collection_for_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            _make_platform_devices_root(fixture_root)
            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_devices()

        self.assertEqual(result.data, ())
        self.assertEqual(result.warnings, ())

    def test_collect_devices_reports_missing_platform_devices_directory(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_devices()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICES_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices",
        )
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

    def test_collect_devices_reports_platform_devices_read_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(sysfs_root=Path("/fixture/sys"))

        with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
            result = provider.collect_devices()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICES_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices",
        )

    def test_collect_devices_reports_per_entry_read_error_as_partial_data(self) -> None:
        provider = LocalLinuxRuntimeProvider(sysfs_root=Path("/fixture/sys"))
        entries = (
            _FakePathEntry("device-a", is_directory=True),
            _FakePathEntry("device-b", error=PermissionError("denied")),
            _FakePathEntry("device-c", is_directory=True),
            _FakePathEntry("not-a-device", is_directory=False),
        )

        with patch.object(Path, "iterdir", return_value=entries):
            result = provider.collect_devices()

        self.assertEqual(
            tuple(device.name for device in result.data),
            ("device-a", "device-c"),
        )
        self.assertEqual(
            tuple(device.sysfs_path for device in result.data),
            (
                "/sys/bus/platform/devices/device-a",
                "/sys/bus/platform/devices/device-c",
            ),
        )
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICE_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices/device-b",
        )

    def test_collect_devices_does_not_assume_platform_resource_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            devices_root = _make_platform_devices_root(fixture_root)
            device = devices_root / "resource-looking-device"
            device.mkdir()
            (device / "resource").write_text(
                "0x0000000000001000 0x0000000000001fff 0x0000000000000200\n",
                encoding="utf-8",
            )

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "resource-looking-device")
        self.assertEqual(result.data[0].resources, ())
        self.assertEqual(result.warnings, ())

    def test_collect_drivers_enumerates_bound_platform_device(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            sysfs_devices_root = _make_sysfs_devices_root(fixture_root)
            driver = drivers_root / "serial8250"
            driver.mkdir()
            bound_link = driver / "107d001000.serial"
            bound_link.touch()
            bound_target = sysfs_devices_root / "platform" / "107d001000.serial"
            bound_target.mkdir(parents=True)

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks({bound_link: bound_target}):
                result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)

        driver_model = result.data[0]
        self.assertIsInstance(driver_model, RuntimeDriver)
        self.assertEqual(driver_model.name, "serial8250")
        self.assertEqual(
            driver_model.sysfs_path,
            "/sys/bus/platform/drivers/serial8250",
        )
        self.assertEqual(driver_model.bus, "platform")
        self.assertEqual(
            driver_model.bound_device_paths,
            ("/sys/bus/platform/devices/107d001000.serial",),
        )
        self.assertIsNone(driver_model.module_name)
        self.assertNotIn(str(fixture_root), driver_model.sysfs_path)
        self.assertNotIn(str(fixture_root), driver_model.bound_device_paths[0])

    def test_collect_drivers_preserves_multiple_bound_device_order(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            sysfs_devices_root = _make_sysfs_devices_root(fixture_root)
            driver = drivers_root / "bcm2835-clk"
            driver.mkdir()
            first_link = driver / "1000fff000.mmc"
            second_link = driver / "107d001000.serial"
            first_link.touch()
            second_link.touch()
            first_target = sysfs_devices_root / "platform" / first_link.name
            second_target = sysfs_devices_root / "platform" / second_link.name
            first_target.mkdir(parents=True)
            second_target.mkdir(parents=True)

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {
                    second_link: second_target,
                    first_link: first_target,
                }
            ):
                result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            result.data[0].bound_device_paths,
            (
                "/sys/bus/platform/devices/1000fff000.mmc",
                "/sys/bus/platform/devices/107d001000.serial",
            ),
        )

    def test_collect_drivers_keeps_driver_with_no_bound_devices(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            driver = drivers_root / "unbound-driver"
            driver.mkdir()
            bind = driver / "bind"
            unbind = driver / "unbind"
            uevent = driver / "uevent"
            bind.touch()
            unbind.touch()
            uevent.touch()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {},
                non_symlinks={bind, unbind, uevent},
            ):
                result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "unbound-driver")
        self.assertEqual(result.data[0].bound_device_paths, ())

    def test_collect_drivers_sorts_multiple_drivers_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            (drivers_root / "serial8250").mkdir()
            (drivers_root / "bcm2835-clk").mkdir()
            (drivers_root / "fixed-regulator").mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            tuple(driver.name for driver in result.data),
            ("bcm2835-clk", "fixed-regulator", "serial8250"),
        )

    def test_collect_drivers_ignores_module_and_control_entries(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            sysfs_devices_root = _make_sysfs_devices_root(fixture_root)
            module_root = fixture_root / "sys" / "module"
            module_root.mkdir(parents=True)
            driver = drivers_root / "serial8250"
            driver.mkdir()
            bound_link = driver / "107d001000.serial"
            module_link = driver / "module"
            bind = driver / "bind"
            unbind = driver / "unbind"
            uevent = driver / "uevent"
            bound_link.touch()
            module_link.touch()
            bind.touch()
            unbind.touch()
            uevent.touch()
            bound_target = sysfs_devices_root / "platform" / bound_link.name
            module_target = module_root / "serial8250"
            bound_target.mkdir(parents=True)
            module_target.mkdir()

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {
                    bound_link: bound_target,
                    module_link: module_target,
                },
                non_symlinks={bind, unbind, uevent},
            ):
                result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(
            result.data[0].bound_device_paths,
            ("/sys/bus/platform/devices/107d001000.serial",),
        )
        self.assertIsNone(result.data[0].module_name)

    def test_collect_drivers_ignores_broken_module_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            module_root = fixture_root / "sys" / "module"
            module_root.mkdir(parents=True)
            driver = drivers_root / "serial8250"
            driver.mkdir()
            module_link = driver / "module"
            module_link.touch()
            module_target = module_root / "serial8250"

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {module_link: module_target},
                resolve_errors={
                    module_link: FileNotFoundError("broken module symlink"),
                },
            ):
                result = provider.collect_drivers()

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].bound_device_paths, ())
        self.assertIsNone(result.data[0].module_name)

    def test_collect_drivers_reports_broken_bound_device_link(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            sysfs_devices_root = _make_sysfs_devices_root(fixture_root)
            driver = drivers_root / "serial8250"
            driver.mkdir()
            broken_link = driver / "broken-device"
            broken_link.touch()
            broken_target = sysfs_devices_root / "platform" / "broken-device"

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {broken_link: broken_target},
                resolve_errors={
                    broken_link: FileNotFoundError("broken symlink"),
                },
            ):
                result = provider.collect_drivers()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "serial8250")
        self.assertEqual(result.data[0].bound_device_paths, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DRIVER_BOUND_DEVICE_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/drivers/serial8250/broken-device",
        )
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

    def test_collect_drivers_keeps_valid_bound_devices_when_one_link_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            drivers_root = _make_platform_drivers_root(fixture_root)
            sysfs_devices_root = _make_sysfs_devices_root(fixture_root)
            driver = drivers_root / "serial8250"
            driver.mkdir()
            valid_link = driver / "107d001000.serial"
            broken_link = driver / "broken-device"
            valid_link.touch()
            broken_link.touch()
            valid_target = sysfs_devices_root / "platform" / valid_link.name
            broken_target = sysfs_devices_root / "platform" / broken_link.name
            valid_target.mkdir(parents=True)

            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            with _patched_driver_symlinks(
                {
                    valid_link: valid_target,
                    broken_link: broken_target,
                },
                resolve_errors={
                    broken_link: FileNotFoundError("broken symlink"),
                },
            ):
                result = provider.collect_drivers()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(
            result.data[0].bound_device_paths,
            ("/sys/bus/platform/devices/107d001000.serial",),
        )
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DRIVER_BOUND_DEVICE_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/drivers/serial8250/broken-device",
        )

    def test_collect_drivers_reports_missing_platform_drivers_directory(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            provider = LocalLinuxRuntimeProvider(sysfs_root=fixture_root / "sys")
            result = provider.collect_drivers()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DRIVERS_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/drivers",
        )
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

    def test_collect_drivers_reports_platform_drivers_read_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(sysfs_root=Path("/fixture/sys"))

        with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
            result = provider.collect_drivers()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DRIVERS_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/drivers",
        )

    def test_collect_drivers_reports_driver_directory_read_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(sysfs_root=Path("/fixture/sys"))
        drivers_root = Path("/fixture/sys") / "bus/platform/drivers"

        def iterdir(path: Path):
            if path == drivers_root:
                return (_FakePathEntry("secret-driver", is_directory=True),)
            if path == drivers_root / "secret-driver":
                raise PermissionError("denied")
            raise FileNotFoundError(path)

        with patch.object(Path, "iterdir", autospec=True, side_effect=iterdir):
            result = provider.collect_drivers()

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0].name, "secret-driver")
        self.assertEqual(result.data[0].bound_device_paths, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DRIVER_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/drivers/secret-driver",
        )

    def test_collect_iomem_reads_proc_iomem_tree(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            proc_root = fixture_root / "proc"
            proc_root.mkdir()
            (proc_root / "iomem").write_text(
                "\n".join(
                    (
                        "00000000-3fffffff : System RAM",
                        "  00080000-001fffff : Kernel code",
                        "40000000-40000fff : device-a",
                    )
                ),
                encoding="utf-8",
            )

            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)
            result = provider.collect_iomem()

        self.assertEqual(result.warnings, ())
        self.assertEqual(len(result.data), 2)
        self.assertIsInstance(result.data[0], IomemRegion)
        self.assertEqual(result.data[0].name, "System RAM")
        self.assertEqual(result.data[0].children[0].name, "Kernel code")
        self.assertEqual(result.data[1].name, "device-a")

    def test_collect_iomem_reports_missing_proc_iomem_as_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            provider = LocalLinuxRuntimeProvider(proc_root=fixture_root / "proc")
            result = provider.collect_iomem()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_IOMEM_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/iomem")
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

    def test_collect_iomem_reports_proc_iomem_read_error(self) -> None:
        provider = LocalLinuxRuntimeProvider(proc_root=Path("/fixture/proc"))

        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = provider.collect_iomem()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "PROC_IOMEM_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/proc/iomem")

    def test_collect_iomem_reports_redacted_proc_iomem_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            proc_root = fixture_root / "proc"
            proc_root.mkdir()
            (proc_root / "iomem").write_text(
                "\n".join(
                    (
                        "00000000-00000000 : System RAM",
                        "  00000000-00000000 : Kernel code",
                        "00000000-00000000 : reserved",
                    )
                ),
                encoding="utf-8",
            )

            provider = LocalLinuxRuntimeProvider(proc_root=proc_root)
            result = provider.collect_iomem()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "PROC_IOMEM_ADDRESSES_REDACTED",
        )
        self.assertEqual(result.warnings[0].source_path, "/proc/iomem")
        self.assertNotIn(str(fixture_root), result.warnings[0].message)

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
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            _make_platform_devices_root(fixture_root)
            _make_platform_drivers_root(fixture_root)
            proc_root = fixture_root / "proc"
            proc_root.mkdir()
            (proc_root / "iomem").write_text("", encoding="utf-8")
            provider: RuntimeProvider = LocalLinuxRuntimeProvider(
                sysfs_root=fixture_root / "sys",
                proc_root=proc_root,
            )

            system_info = provider.collect_system_info()
            devices = provider.collect_devices()
            drivers = provider.collect_drivers()
            iomem = provider.collect_iomem()

        self.assertIsInstance(system_info, RuntimeCollection)
        self.assertIsInstance(system_info.data, RuntimeSystemInfo)
        self.assertIsInstance(devices, RuntimeCollection)
        self.assertEqual(
            tuple(isinstance(device, RuntimeDevice) for device in devices.data),
            (),
        )
        self.assertEqual(devices.data, ())
        self.assertEqual(devices.warnings, ())
        self.assertEqual(drivers.data, ())
        self.assertEqual(
            tuple(isinstance(driver, RuntimeDriver) for driver in drivers.data),
            (),
        )
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


class _PatchedDriverSymlinks:
    def __init__(
        self,
        bindings: dict[Path, Path | OSError],
        *,
        resolve_errors: dict[Path, OSError] | None = None,
        non_symlinks: set[Path] | None = None,
    ) -> None:
        self._bindings = bindings
        self._resolve_errors = resolve_errors or {}
        self._non_symlinks = non_symlinks or set()
        self._patches = (
            patch.object(
                Path,
                "readlink",
                autospec=True,
                side_effect=self._readlink,
            ),
            patch.object(
                Path,
                "resolve",
                autospec=True,
                side_effect=self._resolve,
            ),
        )

    def __enter__(self) -> "_PatchedDriverSymlinks":
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *args: object) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()

    def _readlink(self, path: Path) -> Path:
        if path in self._non_symlinks:
            raise OSError(errno.EINVAL, "not a symlink")

        if path not in self._bindings:
            raise FileNotFoundError(path)

        target = self._bindings[path]
        if isinstance(target, OSError):
            raise target
        return target

    def _resolve(self, path: Path, strict: bool = False) -> Path:
        if path in self._resolve_errors:
            raise self._resolve_errors[path]

        target = self._bindings[path]
        if isinstance(target, OSError):
            raise target
        return target


def _patched_driver_symlinks(
    bindings: dict[Path, Path | OSError],
    *,
    resolve_errors: dict[Path, OSError] | None = None,
    non_symlinks: set[Path] | None = None,
) -> _PatchedDriverSymlinks:
    return _PatchedDriverSymlinks(
        bindings,
        resolve_errors=resolve_errors,
        non_symlinks=non_symlinks,
    )


class _FakePathEntry:
    def __init__(
        self,
        name: str,
        *,
        is_directory: bool = False,
        error: OSError | None = None,
    ) -> None:
        self.name = name
        self._is_directory = is_directory
        self._error = error

    def is_dir(self) -> bool:
        if self._error is not None:
            raise self._error
        return self._is_directory


def _make_platform_devices_root(fixture_root: Path) -> Path:
    devices_root = fixture_root / "sys" / "bus" / "platform" / "devices"
    devices_root.mkdir(parents=True)
    return devices_root


def _make_platform_drivers_root(fixture_root: Path) -> Path:
    drivers_root = fixture_root / "sys" / "bus" / "platform" / "drivers"
    drivers_root.mkdir(parents=True)
    return drivers_root


def _make_sysfs_devices_root(fixture_root: Path) -> Path:
    devices_root = fixture_root / "sys" / "devices"
    devices_root.mkdir(parents=True)
    return devices_root
