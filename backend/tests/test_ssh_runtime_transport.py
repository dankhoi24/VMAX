from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.runtime import LinuxRuntimeProvider, RuntimeTransportError
from app.runtime.config import runtime_provider_from_environment
from app.runtime.ssh_transport import (
    ParamikoSshSession,
    SshCommandResult,
    SshRuntimeTransport,
)
from app.runtime.transport import RuntimeTransportUnavailable


class SshRuntimeTransportTest(unittest.TestCase):
    def test_paths_use_target_namespace(self) -> None:
        transport = SshRuntimeTransport(host="rcar", session=_FakeSshSession({}))

        self.assertEqual(transport.sysfs_root, Path("/sys"))
        self.assertEqual(transport.proc_root, Path("/proc"))
        self.assertEqual(
            transport.sysfs_path("bus/platform/devices"),
            Path("/sys/bus/platform/devices"),
        )
        self.assertEqual(transport.proc_path("iomem"), Path("/proc/iomem"))

    def test_rejects_invalid_connection_and_root_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "host must not be empty"):
            SshRuntimeTransport(host="", session=_FakeSshSession({}))

        with self.assertRaisesRegex(ValueError, "port must be positive"):
            SshRuntimeTransport(host="rcar", port=0, session=_FakeSshSession({}))

        with self.assertRaisesRegex(ValueError, "absolute target path"):
            SshRuntimeTransport(
                host="rcar",
                sysfs_root="sys",
                session=_FakeSshSession({}),
            )

    def test_accepts_user_at_host_target(self) -> None:
        transport = SshRuntimeTransport(
            host="root@rcar",
            session=_FakeSshSession({}),
        )

        self.assertEqual(transport.host, "rcar")
        self.assertEqual(transport.user, "root")

    def test_remote_filesystem_primitives(self) -> None:
        session = _FakeSshSession(
            {
                "vmax:ssh-runtime:iterdir": SshCommandResult(
                    returncode=0,
                    stdout="device-b\ndevice-a\n",
                ),
                "vmax:ssh-runtime:is_dir": SshCommandResult(returncode=0),
                "vmax:ssh-runtime:readlink": SshCommandResult(
                    returncode=0,
                    stdout="../../drivers/serial8250\n",
                ),
                "vmax:ssh-runtime:resolve": SshCommandResult(
                    returncode=0,
                    stdout="/sys/bus/platform/drivers/serial8250\n",
                ),
                "vmax:ssh-runtime:read_text": SshCommandResult(
                    returncode=0,
                    stdout="console=ttySC0\n",
                ),
            }
        )
        transport = SshRuntimeTransport(host="rcar", session=session)

        device_root = Path("/sys/bus/platform/devices")
        self.assertEqual(
            transport.iterdir(device_root),
            (device_root / "device-b", device_root / "device-a"),
        )
        self.assertTrue(transport.is_dir(device_root / "device-a"))
        self.assertEqual(
            transport.readlink(device_root / "device-a" / "driver"),
            Path("../../drivers/serial8250"),
        )
        self.assertEqual(
            transport.resolve(device_root / "device-a" / "driver", strict=True),
            Path("/sys/bus/platform/drivers/serial8250"),
        )
        self.assertEqual(
            transport.read_text(Path("/proc/cmdline"), encoding="utf-8"),
            "console=ttySC0\n",
        )
        self.assertIn("/sys/bus/platform/devices", session.scripts[0])

    def test_uname_and_hostname_come_from_remote_target(self) -> None:
        session = _FakeSshSession(
            {
                "vmax:ssh-runtime:uname": SshCommandResult(
                    returncode=0,
                    stdout="Linux\n6.12.80\n#1 SMP PREEMPT\naarch64\n",
                ),
                "vmax:ssh-runtime:hostname": SshCommandResult(
                    returncode=0,
                    stdout="x5h\n",
                ),
            }
        )
        transport = SshRuntimeTransport(host="rcar", session=session)

        uname = transport.uname()

        self.assertEqual(uname.sysname, "Linux")
        self.assertEqual(uname.release, "6.12.80")
        self.assertEqual(uname.version, "#1 SMP PREEMPT")
        self.assertEqual(uname.machine, "aarch64")
        self.assertEqual(transport.hostname(), "x5h")

    def test_remote_errors_map_to_runtime_transport_contract(self) -> None:
        missing = SshRuntimeTransport(
            host="rcar",
            session=_FakeSshSession(
                {
                    "vmax:ssh-runtime:read_text": SshCommandResult(returncode=42),
                }
            ),
        )
        denied = SshRuntimeTransport(
            host="rcar",
            session=_FakeSshSession(
                {
                    "vmax:ssh-runtime:read_text": SshCommandResult(returncode=43),
                }
            ),
        )
        failed = SshRuntimeTransport(
            host="rcar",
            session=_FakeSshSession(
                {
                    "vmax:ssh-runtime:read_text": SshCommandResult(
                        returncode=99,
                        stderr="remote exploded",
                    ),
                }
            ),
        )

        with self.assertRaises(FileNotFoundError):
            missing.read_text(Path("/proc/missing"), encoding="utf-8")
        with self.assertRaises(PermissionError):
            denied.read_text(Path("/proc/secret"), encoding="utf-8")
        with self.assertRaises(RuntimeTransportError):
            failed.read_text(Path("/proc/iomem"), encoding="utf-8")

    def test_provider_returns_runtime_warning_for_ssh_failure(self) -> None:
        transport = SshRuntimeTransport(
            host="rcar",
            session=_FailingSshSession(),
        )
        provider = LinuxRuntimeProvider(transport)

        result = provider.collect_devices()

        self.assertEqual(result.data, ())
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].code, "SYSFS_PLATFORM_DEVICES_READ_FAILED")
        self.assertEqual(result.warnings[0].source_path, "/sys/bus/platform/devices")

    def test_linux_provider_collects_runtime_data_through_ssh_transport(self) -> None:
        transport = SshRuntimeTransport(host="rcar", session=_RuntimeFixtureSession())
        provider = LinuxRuntimeProvider(transport)

        metadata = provider.collect_system_info()
        devices = provider.collect_devices()
        drivers = provider.collect_drivers()
        iomem = provider.collect_iomem()
        interrupts = provider.collect_interrupts()

        self.assertEqual(metadata.warnings, ())
        self.assertEqual(metadata.data.hostname, "x5h")
        self.assertEqual(metadata.data.machine, "aarch64")
        self.assertEqual(metadata.data.architecture, "arm64")
        self.assertEqual(metadata.data.cmdline, "console=ttySC0")
        self.assertEqual(devices.warnings, ())
        self.assertEqual(len(devices.data), 1)
        self.assertEqual(devices.data[0].name, "18800000.mfis")
        self.assertEqual(
            devices.data[0].sysfs_path,
            "/sys/bus/platform/devices/18800000.mfis",
        )
        self.assertEqual(drivers.warnings, ())
        self.assertEqual(len(drivers.data), 1)
        self.assertEqual(drivers.data[0].name, "arm-smmu-v3")
        self.assertEqual(iomem.warnings, ())
        self.assertEqual(len(iomem.data), 1)
        self.assertEqual(iomem.data[0].name, "18800000.mfis")
        self.assertEqual(interrupts.warnings, ())
        self.assertEqual(len(interrupts.data), 1)
        self.assertEqual(interrupts.data[0].irq, 182)

    def test_environment_factory_selects_ssh_provider(self) -> None:
        provider = runtime_provider_from_environment(
            {
                "VMAX_RUNTIME_SSH_TARGET": "192.0.2.10",
                "VMAX_RUNTIME_SSH_USER": "root",
                "VMAX_RUNTIME_SSH_PORT": "2222",
            }
        )

        self.assertIsInstance(provider, LinuxRuntimeProvider)
        self.assertEqual(provider.sysfs_root, Path("/sys"))
        self.assertEqual(provider.proc_root, Path("/proc"))

    def test_environment_factory_accepts_user_at_host_target(self) -> None:
        provider = runtime_provider_from_environment(
            {
                "VMAX_RUNTIME_SSH_TARGET": "root@192.0.2.10",
            }
        )

        self.assertIsInstance(provider, LinuxRuntimeProvider)

    def test_environment_factory_accepts_unknown_host_key_opt_in(self) -> None:
        provider = runtime_provider_from_environment(
            {
                "VMAX_RUNTIME_SSH_TARGET": "root@192.0.2.10",
                "VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY": "1",
            }
        )

        self.assertTrue(provider._transport._session._accept_unknown_host_key)

    def test_environment_factory_rejects_invalid_host_key_bool(self) -> None:
        with self.assertRaisesRegex(ValueError, "ACCEPT_UNKNOWN_HOST_KEY"):
            runtime_provider_from_environment(
                {
                    "VMAX_RUNTIME_SSH_TARGET": "root@192.0.2.10",
                    "VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY": "maybe",
                }
            )

    def test_environment_factory_rejects_invalid_ssh_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "VMAX_RUNTIME_SSH_PORT"):
            runtime_provider_from_environment(
                {
                    "VMAX_RUNTIME_SSH_TARGET": "192.0.2.10",
                    "VMAX_RUNTIME_SSH_PORT": "not-a-port",
                }
            )

    def test_paramiko_session_rejects_unknown_host_key_by_default(self) -> None:
        fake_paramiko = _FakeParamiko()
        session = _make_paramiko_session(accept_unknown_host_key=False)

        with patch.dict(sys.modules, {"paramiko": fake_paramiko}):
            session._connect()

        self.assertTrue(fake_paramiko.last_client.loaded_system_host_keys)
        self.assertIsInstance(
            fake_paramiko.last_client.missing_host_key_policy,
            _FakeRejectPolicy,
        )

    def test_paramiko_session_accepts_unknown_host_key_when_opted_in(self) -> None:
        fake_paramiko = _FakeParamiko()
        session = _make_paramiko_session(accept_unknown_host_key=True)

        with patch.dict(sys.modules, {"paramiko": fake_paramiko}):
            session._connect()

        self.assertTrue(fake_paramiko.last_client.loaded_system_host_keys)
        self.assertIsInstance(
            fake_paramiko.last_client.missing_host_key_policy,
            _FakeAutoAddPolicy,
        )

    def test_readlink_permission_failure_is_not_treated_as_missing(self) -> None:
        transport = SshRuntimeTransport(
            host="rcar",
            session=_ReadlinkPermissionSession(permission_link="driver"),
        )
        provider = LinuxRuntimeProvider(transport)

        result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertIsNone(result.data[0].driver_name)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices/18800000.mfis/driver",
        )

    def test_of_node_readlink_permission_failure_returns_warning(self) -> None:
        transport = SshRuntimeTransport(
            host="rcar",
            session=_ReadlinkPermissionSession(permission_link="of_node"),
        )
        provider = LinuxRuntimeProvider(transport)

        result = provider.collect_devices()

        self.assertEqual(len(result.data), 1)
        self.assertIsNone(result.data[0].of_node_sysfs_path)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(
            result.warnings[0].code,
            "SYSFS_PLATFORM_DEVICE_OF_NODE_READ_FAILED",
        )
        self.assertEqual(
            result.warnings[0].source_path,
            "/sys/bus/platform/devices/18800000.mfis/of_node",
        )


class _FakeSshSession:
    def __init__(self, responses: dict[str, SshCommandResult]) -> None:
        self._responses = responses
        self.scripts: list[str] = []

    def run(self, script: str) -> SshCommandResult:
        self.scripts.append(script)
        for needle, response in self._responses.items():
            if needle in script:
                return response
        raise AssertionError(f"No fake SSH response for script:\n{script}")


class _FailingSshSession:
    def run(self, script: str) -> SshCommandResult:
        raise RuntimeTransportUnavailable("ssh target unavailable")


class _ReadlinkPermissionSession:
    def __init__(self, permission_link: str) -> None:
        self._permission_link = permission_link

    def run(self, script: str) -> SshCommandResult:
        if "vmax:ssh-runtime:iterdir" in script:
            return SshCommandResult(returncode=0, stdout="18800000.mfis\n")
        if "vmax:ssh-runtime:is_dir" in script:
            return SshCommandResult(returncode=0)
        if "vmax:ssh-runtime:readlink" in script and self._permission_link in script:
            return SshCommandResult(returncode=43)
        if "vmax:ssh-runtime:readlink" in script:
            return SshCommandResult(returncode=42)

        raise AssertionError(f"No readlink permission response for script:\n{script}")


class _RuntimeFixtureSession:
    def run(self, script: str) -> SshCommandResult:
        if "vmax:ssh-runtime:uname" in script:
            return SshCommandResult(
                returncode=0,
                stdout="Linux\n6.12.80\n#1 SMP PREEMPT\naarch64\n",
            )
        if "vmax:ssh-runtime:hostname" in script:
            return SshCommandResult(returncode=0, stdout="x5h\n")
        if "vmax:ssh-runtime:read_text" in script and "/proc/cmdline" in script:
            return SshCommandResult(returncode=0, stdout="console=ttySC0\n")
        if "vmax:ssh-runtime:read_text" in script and "/proc/iomem" in script:
            return SshCommandResult(
                returncode=0,
                stdout="18800000-18800fff : 18800000.mfis\n",
            )
        if "vmax:ssh-runtime:read_text" in script and "/proc/interrupts" in script:
            return SshCommandResult(
                returncode=0,
                stdout="182: 0 4291 0 0 GICv3 150 Level imr\n",
            )
        if "vmax:ssh-runtime:read_text" in script and "/sys/kernel/irq/" in script:
            return SshCommandResult(returncode=42)
        if "vmax:ssh-runtime:iterdir" in script and (
            "/sys/bus/platform/devices" in script
        ):
            return SshCommandResult(
                returncode=0,
                stdout="18800000.mfis\nnot-a-device\n",
            )
        if "vmax:ssh-runtime:iterdir" in script and (
            "/sys/bus/platform/drivers/arm-smmu-v3" in script
        ):
            return SshCommandResult(returncode=0, stdout="")
        if "vmax:ssh-runtime:iterdir" in script and (
            "/sys/bus/platform/drivers" in script
        ):
            return SshCommandResult(returncode=0, stdout="arm-smmu-v3\n")
        if "vmax:ssh-runtime:is_dir" in script and "not-a-device" in script:
            return SshCommandResult(returncode=1)
        if "vmax:ssh-runtime:is_dir" in script and "/sys/kernel/irq" in script:
            return SshCommandResult(returncode=1)
        if "vmax:ssh-runtime:is_dir" in script:
            return SshCommandResult(returncode=0)
        if "vmax:ssh-runtime:readlink" in script:
            return SshCommandResult(returncode=42)

        raise AssertionError(f"No runtime fixture SSH response for script:\n{script}")


def _make_paramiko_session(*, accept_unknown_host_key: bool) -> ParamikoSshSession:
    return ParamikoSshSession(
        host="rcar",
        user="root",
        port=22,
        connect_timeout=10.0,
        command_timeout=30.0,
        key_filename=None,
        password=None,
        look_for_keys=True,
        allow_agent=True,
        accept_unknown_host_key=accept_unknown_host_key,
    )


class _FakeParamiko:
    def __init__(self) -> None:
        self.last_client = _FakeSshClient()

    def SSHClient(self) -> "_FakeSshClient":
        return self.last_client

    def AutoAddPolicy(self) -> "_FakeAutoAddPolicy":
        return _FakeAutoAddPolicy()

    def RejectPolicy(self) -> "_FakeRejectPolicy":
        return _FakeRejectPolicy()


class _FakeAutoAddPolicy:
    pass


class _FakeRejectPolicy:
    pass


class _FakeSshClient:
    def __init__(self) -> None:
        self.loaded_system_host_keys = False
        self.missing_host_key_policy: object | None = None

    def load_system_host_keys(self) -> None:
        self.loaded_system_host_keys = True

    def set_missing_host_key_policy(self, policy: object) -> None:
        self.missing_host_key_policy = policy

    def connect(self, **kwargs: object) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
