from __future__ import annotations

import errno
from dataclasses import replace
from pathlib import Path

from app.runtime.model import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeInterrupt,
    RuntimeSystemInfo,
    RuntimeWarning,
)
from app.runtime.iomem import parse_proc_iomem_file
from app.runtime.interrupts import (
    parse_interrupt_actions,
    parse_proc_interrupts_file,
)
from app.runtime.provider import RuntimeProvider
from app.runtime.transport import (
    LocalRuntimeTransport,
    PathInput,
    RuntimeTransport,
    RuntimeTransportUnavailable,
    normalize_relative_path,
)


PLATFORM_DEVICES_PATH = "bus/platform/devices"
PLATFORM_DRIVERS_PATH = "bus/platform/drivers"
SYSFS_DEVICES_RUNTIME_PREFIX = "/sys/devices/"
WINDOWS_NOT_A_REPARSE_POINT = 4390


class LinuxRuntimeProvider(RuntimeProvider):
    """Linux runtime provider backed by a runtime transport.

    Transport roots are access paths used to read files. Domain model paths
    produced by this provider should stay canonical target paths under /sys and
    /proc, even when tests read from fixture roots or future remote targets.
    """

    def __init__(self, transport: RuntimeTransport) -> None:
        self._transport = transport

    @property
    def sysfs_root(self) -> Path:
        return self._transport.sysfs_root

    @property
    def proc_root(self) -> Path:
        return self._transport.proc_root

    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        warnings: list[RuntimeWarning] = []

        uname = self._read_uname(warnings)
        hostname = self._read_hostname(warnings)
        cmdline = self._read_proc_cmdline(warnings)
        machine = getattr(uname, "machine", None) if uname is not None else None

        return RuntimeCollection(
            data=RuntimeSystemInfo(
                hostname=hostname,
                kernel_name=_uname_attr(uname, "sysname"),
                kernel_release=_uname_attr(uname, "release"),
                kernel_version=_uname_attr(uname, "version"),
                machine=machine,
                architecture=_normalize_architecture(machine),
                cmdline=cmdline,
            ),
            warnings=tuple(warnings),
        )

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        warnings: list[RuntimeWarning] = []
        runtime_path = self._sysfs_runtime_path(PLATFORM_DEVICES_PATH)

        try:
            entries = sorted(
                self._transport.iterdir(
                    self._sysfs_access_path(PLATFORM_DEVICES_PATH)
                ),
                key=lambda entry: entry.name,
            )
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DEVICES_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return RuntimeCollection(data=(), warnings=tuple(warnings))

        devices: list[RuntimeDevice] = []
        for entry in entries:
            entry_runtime_path = f"{runtime_path}/{entry.name}"
            try:
                # sysfs device entries are usually symlinks; is_dir follows them.
                if not self._transport.is_dir(entry):
                    continue
            except OSError as error:
                warnings.append(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DEVICE_READ_FAILED",
                        source_path=entry_runtime_path,
                        message=(
                            f"Unable to inspect {entry_runtime_path}: "
                            f"{_format_error(error)}"
                        ),
                    )
                )
                continue

            driver_name, driver_path = self._read_platform_device_driver(
                entry.name,
                warnings,
            )
            of_node_sysfs_path = self._read_platform_device_of_node(
                entry.name,
                warnings,
            )
            devices.append(
                RuntimeDevice(
                    name=entry.name,
                    sysfs_path=entry_runtime_path,
                    bus="platform",
                    driver_name=driver_name,
                    driver_path=driver_path,
                    of_node_sysfs_path=of_node_sysfs_path,
                )
            )

        return RuntimeCollection(data=tuple(devices), warnings=tuple(warnings))

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        warnings: list[RuntimeWarning] = []
        runtime_path = self._sysfs_runtime_path(PLATFORM_DRIVERS_PATH)

        try:
            entries = sorted(
                self._transport.iterdir(
                    self._sysfs_access_path(PLATFORM_DRIVERS_PATH)
                ),
                key=lambda entry: entry.name,
            )
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DRIVERS_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return RuntimeCollection(data=(), warnings=tuple(warnings))

        drivers: list[RuntimeDriver] = []
        for entry in entries:
            entry_runtime_path = f"{runtime_path}/{entry.name}"
            try:
                if not self._transport.is_dir(entry):
                    continue
            except OSError as error:
                warnings.append(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DRIVER_READ_FAILED",
                        source_path=entry_runtime_path,
                        message=(
                            f"Unable to inspect {entry_runtime_path}: "
                            f"{_format_error(error)}"
                        ),
                    )
                )
                continue

            drivers.append(
                RuntimeDriver(
                    name=entry.name,
                    sysfs_path=entry_runtime_path,
                    bus="platform",
                    bound_device_paths=self._read_platform_driver_bound_devices(
                        entry.name,
                        warnings,
                    ),
                )
            )

        return RuntimeCollection(data=tuple(drivers), warnings=tuple(warnings))

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        runtime_path = self._proc_runtime_path("iomem")
        try:
            text = self._transport.read_text(
                self._proc_access_path("iomem"),
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="PROC_IOMEM_READ_FAILED",
                        source_path=runtime_path,
                        message=(
                            f"Unable to read {runtime_path}: "
                            f"{_format_error(error)}"
                        ),
                    ),
                ),
            )

        return parse_proc_iomem_file(text, runtime_path)

    def collect_interrupts(self) -> RuntimeCollection[tuple[RuntimeInterrupt, ...]]:
        runtime_path = self._proc_runtime_path("interrupts")
        try:
            text = self._transport.read_text(
                self._proc_access_path("interrupts"),
                encoding="utf-8",
            )
        except (OSError, UnicodeError) as error:
            return RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="PROC_INTERRUPTS_READ_FAILED",
                        source_path=runtime_path,
                        message=(
                            f"Unable to read {runtime_path}: "
                            f"{_format_error(error)}"
                        ),
                    ),
                ),
            )

        parsed = parse_proc_interrupts_file(text, runtime_path)
        warnings = list(parsed.warnings)
        if self._sysfs_irq_root_available(warnings):
            interrupts = tuple(
                self._enrich_interrupt_from_sysfs(interrupt, warnings)
                for interrupt in parsed.data
            )
        else:
            interrupts = parsed.data

        return RuntimeCollection(data=interrupts, warnings=tuple(warnings))

    def _sysfs_access_path(self, relative_path: PathInput) -> Path:
        return self._transport.sysfs_path(relative_path)

    def _proc_access_path(self, relative_path: PathInput) -> Path:
        return self._transport.proc_path(relative_path)

    def _sysfs_runtime_path(self, relative_path: PathInput) -> str:
        return _runtime_path("/sys", relative_path, "sysfs relative_path")

    def _proc_runtime_path(self, relative_path: PathInput) -> str:
        return _runtime_path("/proc", relative_path, "proc relative_path")

    def _read_platform_device_driver(
        self,
        device_name: str,
        warnings: list[RuntimeWarning],
    ) -> tuple[str | None, str | None]:
        relative_path = f"{PLATFORM_DEVICES_PATH}/{device_name}/driver"
        runtime_path = self._sysfs_runtime_path(relative_path)
        driver_link = self._sysfs_access_path(relative_path)

        try:
            self._transport.readlink(driver_link)
        except FileNotFoundError:
            return None, None
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to inspect driver binding for {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None, None

        try:
            target = self._transport.resolve(driver_link, strict=True)
            driver_path = self._sysfs_runtime_path_from_access_path(target)
        except (OSError, ValueError) as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to resolve driver binding for {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None, None

        return target.name, driver_path

    def _read_platform_device_of_node(
        self,
        device_name: str,
        warnings: list[RuntimeWarning],
    ) -> str | None:
        relative_path = f"{PLATFORM_DEVICES_PATH}/{device_name}/of_node"
        runtime_path = self._sysfs_runtime_path(relative_path)
        of_node_link = self._sysfs_access_path(relative_path)

        try:
            self._transport.readlink(of_node_link)
        except FileNotFoundError:
            return None
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DEVICE_OF_NODE_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to inspect of_node link for {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None

        try:
            target = self._transport.resolve(of_node_link, strict=True)
            return self._sysfs_runtime_path_from_access_path(target)
        except (OSError, ValueError) as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DEVICE_OF_NODE_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to resolve of_node link for {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None

    def _read_platform_driver_bound_devices(
        self,
        driver_name: str,
        warnings: list[RuntimeWarning],
    ) -> tuple[str, ...]:
        relative_path = f"{PLATFORM_DRIVERS_PATH}/{driver_name}"
        runtime_path = self._sysfs_runtime_path(relative_path)

        try:
            entries = sorted(
                self._transport.iterdir(self._sysfs_access_path(relative_path)),
                key=lambda entry: entry.name,
            )
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_PLATFORM_DRIVER_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return ()

        bound_device_paths: list[str] = []
        for entry in entries:
            if entry.name == "module":
                continue

            entry_runtime_path = f"{runtime_path}/{entry.name}"
            try:
                self._transport.readlink(entry)
            except OSError as error:
                if _is_not_symlink_error(error):
                    continue
                warnings.append(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DRIVER_BOUND_DEVICE_READ_FAILED",
                        source_path=entry_runtime_path,
                        message=(
                            f"Unable to inspect bound device link "
                            f"{entry_runtime_path}: {_format_error(error)}"
                        ),
                    )
                )
                continue

            try:
                target = self._transport.resolve(entry, strict=True)
                target_runtime_path = self._sysfs_runtime_path_from_access_path(target)
            except (OSError, ValueError) as error:
                warnings.append(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DRIVER_BOUND_DEVICE_READ_FAILED",
                        source_path=entry_runtime_path,
                        message=(
                            f"Unable to resolve bound device link "
                            f"{entry_runtime_path}: {_format_error(error)}"
                        ),
                    )
                )
                continue

            if not target_runtime_path.startswith(SYSFS_DEVICES_RUNTIME_PREFIX):
                continue

            bound_device_paths.append(
                self._sysfs_runtime_path(f"{PLATFORM_DEVICES_PATH}/{entry.name}")
            )

        return tuple(bound_device_paths)

    def _sysfs_irq_root_available(self, warnings: list[RuntimeWarning]) -> bool:
        runtime_path = self._sysfs_runtime_path("kernel/irq")
        try:
            return self._transport.is_dir(self._sysfs_access_path("kernel/irq"))
        except (FileNotFoundError, NotADirectoryError):
            return False
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_IRQ_METADATA_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to inspect {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return False

    def _enrich_interrupt_from_sysfs(
        self,
        interrupt: RuntimeInterrupt,
        warnings: list[RuntimeWarning],
    ) -> RuntimeInterrupt:
        actions_text = self._read_sysfs_irq_metadata(
            interrupt.irq,
            "actions",
            warnings,
        )
        chip_name = self._read_sysfs_irq_metadata(
            interrupt.irq,
            "chip_name",
            warnings,
        )
        hwirq_text = self._read_sysfs_irq_metadata(
            interrupt.irq,
            "hwirq",
            warnings,
        )
        trigger = self._read_sysfs_irq_metadata(
            interrupt.irq,
            "type",
            warnings,
        )
        metadata = list(interrupt.metadata)

        for field_name in ("smp_affinity_list", "effective_affinity_list"):
            value = self._read_sysfs_irq_metadata(
                interrupt.irq,
                field_name,
                warnings,
            )
            if value is not None:
                metadata.append((field_name, value))

        hardware_irq = interrupt.hardware_irq
        if hwirq_text is not None:
            try:
                hardware_irq = int(hwirq_text, 0)
            except ValueError as error:
                runtime_path = self._sysfs_runtime_path(
                    f"kernel/irq/{interrupt.irq}/hwirq"
                )
                warnings.append(
                    RuntimeWarning(
                        code="SYSFS_IRQ_METADATA_PARSE_FAILED",
                        source_path=runtime_path,
                        message=(
                            f"Unable to parse {runtime_path}: "
                            f"{_format_error(error)}"
                        ),
                    )
                )

        actions = interrupt.actions
        if actions_text is not None:
            actions = parse_interrupt_actions(actions_text)

        return replace(
            interrupt,
            controller=chip_name or interrupt.controller,
            hardware_irq=hardware_irq,
            trigger=trigger or interrupt.trigger,
            actions=actions,
            metadata=tuple(metadata),
        )

    def _read_sysfs_irq_metadata(
        self,
        irq: int,
        field_name: str,
        warnings: list[RuntimeWarning],
    ) -> str | None:
        relative_path = f"kernel/irq/{irq}/{field_name}"
        runtime_path = self._sysfs_runtime_path(relative_path)

        try:
            value = self._transport.read_text(
                self._sysfs_access_path(relative_path),
                encoding="utf-8",
            ).strip()
        except (FileNotFoundError, NotADirectoryError):
            return None
        except (OSError, UnicodeError) as error:
            warnings.append(
                RuntimeWarning(
                    code="SYSFS_IRQ_METADATA_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None

        return value or None

    def _sysfs_runtime_path_from_access_path(self, access_path: Path) -> str:
        try:
            relative_path = access_path.relative_to(self.sysfs_root)
        except ValueError as error:
            raise ValueError("sysfs access path is outside sysfs_root") from error
        return self._sysfs_runtime_path(relative_path)

    def _read_proc_cmdline(self, warnings: list[RuntimeWarning]) -> str | None:
        runtime_path = self._proc_runtime_path("cmdline")
        try:
            return self._transport.read_text(
                self._proc_access_path("cmdline"),
                encoding="utf-8",
            ).strip()
        except (OSError, UnicodeError) as error:
            warnings.append(
                RuntimeWarning(
                    code="PROC_CMDLINE_READ_FAILED",
                    source_path=runtime_path,
                    message=(
                        f"Unable to read {runtime_path}: "
                        f"{_format_error(error)}"
                    ),
                )
            )
            return None

    def _read_uname(self, warnings: list[RuntimeWarning]) -> object | None:
        try:
            return self._transport.uname()
        except RuntimeTransportUnavailable as error:
            warnings.append(
                RuntimeWarning(
                    code="UNAME_READ_FAILED",
                    message=f"Unable to read uname: {error}",
                )
            )
            return None
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="UNAME_READ_FAILED",
                    message=f"Unable to read uname: {error}",
                )
            )
            return None

    def _read_hostname(self, warnings: list[RuntimeWarning]) -> str | None:
        try:
            return self._transport.hostname()
        except OSError as error:
            warnings.append(
                RuntimeWarning(
                    code="HOSTNAME_READ_FAILED",
                    message=f"Unable to read hostname: {error}",
                )
            )
            return None


class LocalLinuxRuntimeProvider(LinuxRuntimeProvider):
    """Compatibility wrapper for collecting Linux runtime data from this host."""

    def __init__(
        self,
        sysfs_root: PathInput = Path("/sys"),
        proc_root: PathInput = Path("/proc"),
    ) -> None:
        super().__init__(
            LocalRuntimeTransport(
                sysfs_root=sysfs_root,
                proc_root=proc_root,
            )
        )


def _runtime_path(root: str, relative_path: PathInput, field_name: str) -> str:
    path = normalize_relative_path(relative_path, field_name)
    return f"{root}/{path.as_posix()}"


def _uname_attr(uname: object | None, name: str) -> str | None:
    return getattr(uname, name, None) if uname is not None else None


def _normalize_architecture(machine: str | None) -> str | None:
    if machine is None:
        return None

    normalized = machine.lower()
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    if normalized in {"x86_64", "amd64"}:
        return "x86_64"
    if normalized == "riscv64":
        return "riscv64"
    return normalized


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)


def _is_not_symlink_error(error: OSError) -> bool:
    return (
        getattr(error, "errno", None) == errno.EINVAL
        or getattr(error, "winerror", None) == WINDOWS_NOT_A_REPARSE_POINT
    )
