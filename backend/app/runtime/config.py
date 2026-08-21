from __future__ import annotations

import os
from collections.abc import Mapping

from app.runtime.local_linux import LinuxRuntimeProvider, LocalLinuxRuntimeProvider
from app.runtime.provider import RuntimeProvider
from app.runtime.ssh_transport import SshRuntimeTransport


def runtime_provider_from_environment(
    environ: Mapping[str, str] | None = None,
) -> RuntimeProvider:
    env = environ if environ is not None else os.environ
    target = env.get("VMAX_RUNTIME_SSH_TARGET", "").strip()
    if not target:
        return LocalLinuxRuntimeProvider()

    return LinuxRuntimeProvider(
        SshRuntimeTransport(
            host=target,
            user=_optional(env.get("VMAX_RUNTIME_SSH_USER")),
            port=_parse_port(env.get("VMAX_RUNTIME_SSH_PORT")),
            key_filename=_optional(env.get("VMAX_RUNTIME_SSH_KEY")),
            password=_optional(env.get("VMAX_RUNTIME_SSH_PASSWORD")),
            sysfs_root=env.get("VMAX_RUNTIME_SYSFS_ROOT", "/sys"),
            proc_root=env.get("VMAX_RUNTIME_PROC_ROOT", "/proc"),
            accept_unknown_host_key=_parse_bool(
                env.get("VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY")
            ),
        )
    )


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_port(value: str | None) -> int:
    if value is None or not value.strip():
        return 22
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("VMAX_RUNTIME_SSH_PORT must be an integer") from error
    if port <= 0:
        raise ValueError("VMAX_RUNTIME_SSH_PORT must be positive")
    return port


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    raise ValueError(
        "VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY must be one of "
        "1/0, true/false, yes/no, on/off"
    )
