from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.runtime import (
    LinuxRuntimeProvider,
    LocalRuntimeTransport,
    RuntimeTransportError,
    RuntimeTransportUnavailable,
)


class LocalRuntimeTransportTest(unittest.TestCase):
    def test_default_roots_point_to_linux_runtime_filesystems(self) -> None:
        transport = LocalRuntimeTransport()

        self.assertEqual(transport.sysfs_root, Path("/sys"))
        self.assertEqual(transport.proc_root, Path("/proc"))

    def test_custom_roots_create_access_paths_without_runtime_leak(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            transport = LocalRuntimeTransport(
                sysfs_root=fixture_root / "sys",
                proc_root=fixture_root / "proc",
            )

            self.assertEqual(
                transport.sysfs_path("bus/platform/devices/foo"),
                fixture_root / "sys" / "bus/platform/devices/foo",
            )
            self.assertEqual(
                transport.proc_path("iomem"),
                fixture_root / "proc" / "iomem",
            )

    def test_rejects_empty_and_absolute_paths(self) -> None:
        transport = LocalRuntimeTransport()

        with self.assertRaisesRegex(ValueError, "sysfs_root must not be empty"):
            LocalRuntimeTransport(sysfs_root="")

        with self.assertRaisesRegex(ValueError, "proc_root must not be empty"):
            LocalRuntimeTransport(proc_root="")

        with self.assertRaisesRegex(ValueError, "relative_path must not be empty"):
            transport.sysfs_path("")

        with self.assertRaisesRegex(ValueError, "relative_path must be relative"):
            transport.proc_path("/iomem")

        with self.assertRaisesRegex(ValueError, r"relative_path must not contain '..'"):
            transport.sysfs_path("../proc")

    def test_transport_unavailable_is_transport_io_error(self) -> None:
        self.assertTrue(issubclass(RuntimeTransportError, OSError))
        self.assertTrue(issubclass(RuntimeTransportUnavailable, RuntimeTransportError))

    def test_local_transport_delegates_filesystem_and_os_calls(self) -> None:
        uname = SimpleNamespace(
            sysname="Linux",
            release="6.12.80-v8",
            version="#1 SMP PREEMPT",
            machine="aarch64",
        )

        with tempfile.TemporaryDirectory() as root:
            fixture_root = Path(root)
            sysfs_root = fixture_root / "sys"
            proc_root = fixture_root / "proc"
            device_root = sysfs_root / "bus" / "platform" / "devices"
            device = device_root / "107d001000.serial"
            proc_root.mkdir(parents=True)
            device.mkdir(parents=True)
            (proc_root / "cmdline").write_text("quiet\n", encoding="utf-8")

            transport = LocalRuntimeTransport(
                sysfs_root=sysfs_root,
                proc_root=proc_root,
            )

            with patch(
                "app.runtime.transport.os.uname",
                return_value=uname,
                create=True,
            ):
                with patch(
                    "app.runtime.transport.socket.gethostname",
                    return_value="pi5",
                ):
                    entries = transport.iterdir(device_root)
                    hostname = transport.hostname()
                    runtime_uname = transport.uname()

            self.assertEqual(tuple(entry.name for entry in entries), (device.name,))
            self.assertTrue(transport.is_dir(device))
            self.assertEqual(
                transport.read_text(proc_root / "cmdline", encoding="utf-8"),
                "quiet\n",
            )
            self.assertEqual(hostname, "pi5")
            self.assertEqual(runtime_uname.machine, "aarch64")

    def test_provider_uses_injected_transport_for_runtime_access(self) -> None:
        transport = _FakeRuntimeTransport()
        provider = LinuxRuntimeProvider(transport)

        system_info = provider.collect_system_info()
        devices = provider.collect_devices()
        drivers = provider.collect_drivers()
        iomem = provider.collect_iomem()

        self.assertEqual(system_info.data.hostname, "pi5")
        self.assertEqual(system_info.data.architecture, "arm64")
        self.assertEqual(system_info.data.cmdline, "quiet")
        self.assertEqual(devices.warnings, ())
        self.assertEqual(len(devices.data), 1)
        self.assertEqual(devices.data[0].name, "107d001000.serial")
        self.assertEqual(drivers.warnings, ())
        self.assertEqual(len(drivers.data), 1)
        self.assertEqual(drivers.data[0].name, "serial8250")
        self.assertEqual(iomem.warnings, ())
        self.assertEqual(len(iomem.data), 1)
        self.assertEqual(iomem.data[0].name, "System RAM")
        self.assertIn(("iterdir", "/fixture/sys/bus/platform/devices"), transport.calls)
        self.assertIn(("iterdir", "/fixture/sys/bus/platform/drivers"), transport.calls)
        self.assertIn(("read_text", "/fixture/proc/iomem"), transport.calls)


class _FakeRuntimeTransport:
    def __init__(self) -> None:
        self.sysfs_root = Path("/fixture/sys")
        self.proc_root = Path("/fixture/proc")
        self.calls: list[tuple[str, str]] = []

    def sysfs_path(self, relative_path: str | Path) -> Path:
        return self.sysfs_root / relative_path

    def proc_path(self, relative_path: str | Path) -> Path:
        return self.proc_root / relative_path

    def iterdir(self, path: Path) -> tuple[Path, ...]:
        self.calls.append(("iterdir", path.as_posix()))
        if path == self.sysfs_root / "bus/platform/devices":
            return (path / "107d001000.serial",)
        if path == self.sysfs_root / "bus/platform/drivers":
            return (path / "serial8250",)
        if path == self.sysfs_root / "bus/platform/drivers/serial8250":
            return ()
        raise FileNotFoundError(path)

    def is_dir(self, path: Path) -> bool:
        self.calls.append(("is_dir", path.as_posix()))
        return True

    def readlink(self, path: Path) -> Path:
        self.calls.append(("readlink", path.as_posix()))
        raise FileNotFoundError(path)

    def resolve(self, path: Path, *, strict: bool = False) -> Path:
        self.calls.append(("resolve", path.as_posix()))
        return path

    def read_text(self, path: Path, *, encoding: str) -> str:
        self.calls.append(("read_text", path.as_posix()))
        if path == self.proc_root / "cmdline":
            return "quiet\n"
        if path == self.proc_root / "iomem":
            return "00000000-3fffffff : System RAM\n"
        raise FileNotFoundError(path)

    def uname(self) -> object:
        self.calls.append(("uname", ""))
        return SimpleNamespace(
            sysname="Linux",
            release="6.12.80-v8",
            version="#1 SMP PREEMPT",
            machine="aarch64",
        )

    def hostname(self) -> str:
        self.calls.append(("hostname", ""))
        return "pi5"


if __name__ == "__main__":
    unittest.main()
