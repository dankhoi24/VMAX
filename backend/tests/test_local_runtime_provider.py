from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from app.runtime import (
    LocalLinuxRuntimeProvider,
    RuntimeCollection,
    RuntimeDevice,
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
                {device / "driver": FileNotFoundError("broken symlink")}
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

    def test_collect_devices_reports_driver_resolve_error_as_partial_data(self) -> None:
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
            provider: RuntimeProvider = LocalLinuxRuntimeProvider(
                sysfs_root=fixture_root / "sys",
                proc_root=fixture_root / "proc",
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
    def __init__(self, bindings: dict[Path, Path | OSError]) -> None:
        self._bindings = bindings
        self._patches = (
            patch.object(
                Path,
                "is_symlink",
                autospec=True,
                side_effect=self._is_symlink,
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

    def _is_symlink(self, path: Path) -> bool:
        return path in self._bindings

    def _resolve(self, path: Path, strict: bool = False) -> Path:
        target = self._bindings[path]
        if isinstance(target, OSError):
            raise target
        return target


def _patched_driver_symlinks(
    bindings: dict[Path, Path | OSError],
) -> _PatchedDriverSymlinks:
    return _PatchedDriverSymlinks(bindings)


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
