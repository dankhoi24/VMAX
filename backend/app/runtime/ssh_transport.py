from __future__ import annotations

import errno
import shlex
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

from app.runtime.transport import (
    PathInput,
    RuntimeTransportError,
    RuntimeTransportUnavailable,
    normalize_relative_path,
    normalize_root,
)


_EXIT_MISSING = 42
_EXIT_PERMISSION = 43
_EXIT_NOT_SYMLINK = 44
_EXIT_NOT_DIRECTORY = 45


@dataclass(frozen=True)
class SshCommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class SshCommandSession(Protocol):
    def run(self, script: str) -> SshCommandResult:
        ...


class SshRuntimeTransport:
    """Runtime transport that reads Linux runtime files through SSH."""

    def __init__(
        self,
        host: str,
        *,
        user: str | None = None,
        port: int = 22,
        sysfs_root: PathInput = Path("/sys"),
        proc_root: PathInput = Path("/proc"),
        session: SshCommandSession | None = None,
        connect_timeout: float = 10.0,
        command_timeout: float = 30.0,
        key_filename: str | None = None,
        password: str | None = None,
        look_for_keys: bool = True,
        allow_agent: bool = True,
        accept_unknown_host_key: bool = False,
    ) -> None:
        if not host.strip():
            raise ValueError("host must not be empty")
        if port <= 0:
            raise ValueError("port must be positive")

        host, user = _split_ssh_target(host, user)
        self._host = host
        self._user = user
        self._port = port
        self._sysfs_root = _normalize_remote_root(sysfs_root, "sysfs_root")
        self._proc_root = _normalize_remote_root(proc_root, "proc_root")
        self._session = session or ParamikoSshSession(
            host=host,
            user=user,
            port=port,
            connect_timeout=connect_timeout,
            command_timeout=command_timeout,
            key_filename=key_filename,
            password=password,
            look_for_keys=look_for_keys,
            allow_agent=allow_agent,
            accept_unknown_host_key=accept_unknown_host_key,
        )

    @property
    def host(self) -> str:
        return self._host

    @property
    def user(self) -> str | None:
        return self._user

    @property
    def port(self) -> int:
        return self._port

    @property
    def sysfs_root(self) -> Path:
        return self._sysfs_root

    @property
    def proc_root(self) -> Path:
        return self._proc_root

    def sysfs_path(self, relative_path: PathInput) -> Path:
        return self._sysfs_root / normalize_relative_path(
            relative_path,
            "sysfs relative_path",
        )

    def proc_path(self, relative_path: PathInput) -> Path:
        return self._proc_root / normalize_relative_path(
            relative_path,
            "proc relative_path",
        )

    def iterdir(self, path: Path) -> tuple[Path, ...]:
        stdout = self._run_checked(
            "iterdir",
            path,
            f"""
# vmax:ssh-runtime:iterdir
path={_quote_path(path)}
if [ ! -e "$path" ]; then exit {_EXIT_MISSING}; fi
if [ ! -d "$path" ]; then exit {_EXIT_NOT_DIRECTORY}; fi
LC_ALL=C ls -1A -- "$path"
""",
        )
        return tuple(path / name for name in stdout.splitlines() if name)

    def is_dir(self, path: Path) -> bool:
        result = self._run(
            f"""
# vmax:ssh-runtime:is_dir
path={_quote_path(path)}
if [ -d "$path" ]; then exit 0; fi
exit 1
"""
        )
        if result.returncode == 0:
            return True
        if result.returncode == 1:
            return False
        self._raise_for_result("is_dir", path, result)

    def readlink(self, path: Path) -> Path:
        stdout = self._run_checked(
            "readlink",
            path,
            f"""
# vmax:ssh-runtime:readlink
path={_quote_path(path)}
output=$(readlink -- "$path" 2>&1)
status=$?
if [ "$status" -eq 0 ]; then
    printf '%s\\n' "$output"
    exit 0
fi
case "$output" in
    *[Pp]ermission*[Dd]enied*) exit {_EXIT_PERMISSION} ;;
esac
if [ -e "$path" ]; then exit {_EXIT_NOT_SYMLINK}; fi
exit {_EXIT_MISSING}
""",
        )
        return Path(stdout.strip())

    def resolve(self, path: Path, *, strict: bool = False) -> Path:
        strict_value = "1" if strict else "0"
        stdout = self._run_checked(
            "resolve",
            path,
            f"""
# vmax:ssh-runtime:resolve
path={_quote_path(path)}
strict={strict_value}
if [ "$strict" = "1" ] && [ ! -e "$path" ]; then exit {_EXIT_MISSING}; fi
resolved=$(readlink -f -- "$path") || {{
    if [ "$strict" = "1" ]; then exit {_EXIT_MISSING}; fi
    printf '%s\\n' "$path"
    exit 0
}}
if [ "$strict" = "1" ] && [ ! -e "$resolved" ]; then exit {_EXIT_MISSING}; fi
printf '%s\\n' "$resolved"
""",
        )
        return Path(stdout.strip())

    def read_text(self, path: Path, *, encoding: str) -> str:
        if encoding.lower().replace("_", "-") != "utf-8":
            raise RuntimeTransportError(
                f"SshRuntimeTransport only supports utf-8 text reads, got {encoding}"
            )

        return self._run_checked(
            "read_text",
            path,
            f"""
# vmax:ssh-runtime:read_text
path={_quote_path(path)}
if [ ! -e "$path" ]; then exit {_EXIT_MISSING}; fi
if [ ! -r "$path" ]; then exit {_EXIT_PERMISSION}; fi
cat -- "$path"
""",
        )

    def uname(self) -> object:
        stdout = self._run_checked(
            "uname",
            None,
            """
# vmax:ssh-runtime:uname
uname -s
uname -r
uname -v
uname -m
""",
        )
        lines = stdout.splitlines()
        if len(lines) < 4:
            raise RuntimeTransportError("SSH uname command returned incomplete data")
        return SimpleNamespace(
            sysname=lines[0],
            release=lines[1],
            version=lines[2],
            machine=lines[3],
        )

    def hostname(self) -> str:
        return self._run_checked(
            "hostname",
            None,
            """
# vmax:ssh-runtime:hostname
hostname
""",
        ).strip()

    def close(self) -> None:
        close = getattr(self._session, "close", None)
        if close is not None:
            close()

    def _run_checked(
        self,
        operation: str,
        path: Path | None,
        script: str,
    ) -> str:
        result = self._run(script)
        if result.returncode == 0:
            return result.stdout
        self._raise_for_result(operation, path, result)

    def _run(self, script: str) -> SshCommandResult:
        try:
            return self._session.run(_normalize_script(script))
        except RuntimeTransportError:
            raise
        except OSError:
            raise
        except Exception as error:
            raise RuntimeTransportUnavailable(f"SSH transport failed: {error}") from error

    def _raise_for_result(
        self,
        operation: str,
        path: Path | None,
        result: SshCommandResult,
    ) -> None:
        if result.returncode == _EXIT_MISSING:
            raise FileNotFoundError(str(path or operation))
        if result.returncode == _EXIT_PERMISSION or _looks_like_permission_error(
            result.stderr
        ):
            raise PermissionError(str(path or operation))
        if result.returncode == _EXIT_NOT_SYMLINK:
            raise OSError(errno.EINVAL, "not a symlink", str(path or operation))
        if result.returncode == _EXIT_NOT_DIRECTORY:
            raise NotADirectoryError(str(path or operation))

        message = _format_remote_failure(operation, path, result)
        raise RuntimeTransportError(message)


class ParamikoSshSession:
    """Small persistent Paramiko session wrapper used by SshRuntimeTransport."""

    def __init__(
        self,
        *,
        host: str,
        user: str | None,
        port: int,
        connect_timeout: float,
        command_timeout: float,
        key_filename: str | None,
        password: str | None,
        look_for_keys: bool,
        allow_agent: bool,
        accept_unknown_host_key: bool,
    ) -> None:
        self._host = host
        self._user = user
        self._port = port
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._key_filename = key_filename
        self._password = password
        self._look_for_keys = look_for_keys
        self._allow_agent = allow_agent
        self._accept_unknown_host_key = accept_unknown_host_key
        self._client: object | None = None

    def run(self, script: str) -> SshCommandResult:
        client = self._connect()
        try:
            stdin, stdout, stderr = client.exec_command(
                "sh -s",
                timeout=self._command_timeout,
            )
            stdin.write(script)
            stdin.channel.shutdown_write()
            stdout_data = stdout.read()
            stderr_data = stderr.read()
            return SshCommandResult(
                returncode=stdout.channel.recv_exit_status(),
                stdout=_decode_ssh_output(stdout_data),
                stderr=_decode_ssh_output(stderr_data),
            )
        except Exception as error:
            self.close()
            raise RuntimeTransportUnavailable(
                f"SSH command failed on {self._host}: {error}"
            ) from error

    def close(self) -> None:
        if self._client is None:
            return
        close = getattr(self._client, "close", None)
        if close is not None:
            close()
        self._client = None

    def _connect(self) -> object:
        if self._client is not None:
            return self._client

        try:
            import paramiko  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeTransportUnavailable(
                "Paramiko is required for SshRuntimeTransport. "
                "Install paramiko on the backend host before using SSH runtime."
            ) from error

        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            if self._accept_unknown_host_key:
                policy = paramiko.AutoAddPolicy()
            else:
                policy = paramiko.RejectPolicy()
            client.set_missing_host_key_policy(policy)
            client.connect(
                hostname=self._host,
                username=self._user,
                port=self._port,
                timeout=self._connect_timeout,
                banner_timeout=self._connect_timeout,
                auth_timeout=self._connect_timeout,
                key_filename=self._key_filename,
                password=self._password,
                look_for_keys=self._look_for_keys,
                allow_agent=self._allow_agent,
            )
        except Exception as error:
            raise RuntimeTransportUnavailable(
                f"Unable to open SSH connection to {self._host}: {error}"
            ) from error

        self._client = client
        return client


def _normalize_remote_root(value: PathInput, field_name: str) -> Path:
    path = normalize_root(value, field_name)
    if not path.as_posix().startswith("/"):
        raise ValueError(f"{field_name} must be an absolute target path")
    return path


def _split_ssh_target(host: str, user: str | None) -> tuple[str, str | None]:
    if "@" not in host:
        return host, user

    embedded_user, embedded_host = host.rsplit("@", 1)
    if not embedded_user.strip() or not embedded_host.strip():
        raise ValueError("host must be a host or user@host")
    return embedded_host, user or embedded_user


def _quote_path(path: Path) -> str:
    return shlex.quote(path.as_posix())


def _normalize_script(script: str) -> str:
    return script.strip() + "\n"


def _decode_ssh_output(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _looks_like_permission_error(stderr: str) -> bool:
    return "permission denied" in stderr.lower()


def _format_remote_failure(
    operation: str,
    path: Path | None,
    result: SshCommandResult,
) -> str:
    target = f" for {path.as_posix()}" if path is not None else ""
    detail = result.stderr.strip() or result.stdout.strip() or "no remote output"
    return (
        f"SSH {operation}{target} failed with exit code "
        f"{result.returncode}: {detail}"
    )
