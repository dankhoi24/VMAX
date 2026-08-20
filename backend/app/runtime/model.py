from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


MetadataValue = str | int | bool | None
MetadataItems = tuple[tuple[str, MetadataValue], ...]
T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeWarning:
    code: str
    message: str
    source_path: str | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("RuntimeWarning.code must not be empty")
        if not self.message:
            raise ValueError("RuntimeWarning.message must not be empty")
        if self.source_path is not None:
            _validate_absolute_path(self.source_path, "RuntimeWarning.source_path")


@dataclass(frozen=True)
class RuntimeCollection(Generic[T]):
    data: T
    warnings: tuple[RuntimeWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class RuntimeSystemInfo:
    """Runtime host metadata.

    machine is the raw uname machine; architecture is the VMAX-normalized value.
    """

    hostname: str | None = None
    kernel_name: str | None = None
    kernel_release: str | None = None
    kernel_version: str | None = None
    machine: str | None = None
    architecture: str | None = None
    cmdline: str | None = None


@dataclass(frozen=True)
class RuntimeResource:
    index: int
    start: int
    end: int
    flags: int
    flag_names: tuple[str, ...] = field(default_factory=tuple)
    name: str | None = None

    def __post_init__(self) -> None:
        _validate_index(self.index, "RuntimeResource.index")
        _validate_non_negative_int(self.start, "RuntimeResource.start")
        _validate_non_negative_int(self.end, "RuntimeResource.end")
        _validate_non_negative_int(self.flags, "RuntimeResource.flags")
        if self.end < self.start:
            raise ValueError("RuntimeResource.end must be >= start")
        object.__setattr__(self, "flag_names", _normalize_str_tuple(self.flag_names))
        if self.name is not None and not self.name:
            raise ValueError("RuntimeResource.name must not be empty")

    @property
    def size(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class RuntimeDevice:
    name: str
    sysfs_path: str
    bus: str
    driver_name: str | None = None
    driver_path: str | None = None
    of_node_sysfs_path: str | None = None
    subsystem_path: str | None = None
    modalias: str | None = None
    resources: tuple[RuntimeResource, ...] = field(default_factory=tuple)
    metadata: MetadataItems = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty(self.name, "RuntimeDevice.name")
        _validate_absolute_path(self.sysfs_path, "RuntimeDevice.sysfs_path")
        _validate_non_empty(self.bus, "RuntimeDevice.bus")
        _validate_optional_non_empty(self.driver_name, "RuntimeDevice.driver_name")
        _validate_optional_absolute_path(self.driver_path, "RuntimeDevice.driver_path")
        _validate_optional_absolute_path(
            self.of_node_sysfs_path,
            "RuntimeDevice.of_node_sysfs_path",
        )
        _validate_optional_absolute_path(
            self.subsystem_path,
            "RuntimeDevice.subsystem_path",
        )
        _validate_optional_non_empty(self.modalias, "RuntimeDevice.modalias")
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))


@dataclass(frozen=True)
class RuntimeDriver:
    name: str
    sysfs_path: str
    bus: str
    module_name: str | None = None
    bound_device_paths: tuple[str, ...] = field(default_factory=tuple)
    metadata: MetadataItems = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty(self.name, "RuntimeDriver.name")
        _validate_absolute_path(self.sysfs_path, "RuntimeDriver.sysfs_path")
        _validate_non_empty(self.bus, "RuntimeDriver.bus")
        _validate_optional_non_empty(self.module_name, "RuntimeDriver.module_name")
        bound_device_paths = _normalize_str_tuple(self.bound_device_paths)
        for path in bound_device_paths:
            _validate_absolute_path(path, "RuntimeDriver.bound_device_paths")
        object.__setattr__(self, "bound_device_paths", bound_device_paths)
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))


@dataclass(frozen=True)
class IomemRegion:
    start: int
    end: int
    name: str
    children: tuple["IomemRegion", ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.start, "IomemRegion.start")
        _validate_non_negative_int(self.end, "IomemRegion.end")
        if self.end < self.start:
            raise ValueError("IomemRegion.end must be >= start")
        _validate_non_empty(self.name, "IomemRegion.name")
        children = tuple(self.children)
        for child in children:
            if child.start < self.start or child.end > self.end:
                raise ValueError("IomemRegion.children must be inside parent range")
        object.__setattr__(self, "children", children)

    @property
    def size(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class LinuxRuntimeSnapshot:
    system: RuntimeSystemInfo = field(default_factory=RuntimeSystemInfo)
    devices: tuple[RuntimeDevice, ...] = field(default_factory=tuple)
    drivers: tuple[RuntimeDriver, ...] = field(default_factory=tuple)
    iomem: tuple[IomemRegion, ...] = field(default_factory=tuple)
    warnings: tuple[RuntimeWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "devices", tuple(self.devices))
        object.__setattr__(self, "drivers", tuple(self.drivers))
        object.__setattr__(self, "iomem", tuple(self.iomem))
        object.__setattr__(self, "warnings", tuple(self.warnings))


def _normalize_metadata(value: MetadataItems) -> MetadataItems:
    items: list[tuple[str, MetadataValue]] = []

    for key, item_value in value:
        _validate_non_empty(key, "metadata key")
        if not _is_metadata_value(item_value):
            raise TypeError("metadata value must be str, int, bool, or None")
        items.append((key, item_value))

    return tuple(items)


def _normalize_str_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(value)
    for item in result:
        _validate_non_empty(item, "tuple item")
    return result


def _validate_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _validate_optional_non_empty(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_non_empty(value, field_name)


def _validate_absolute_path(value: str, field_name: str) -> None:
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_optional_absolute_path(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_absolute_path(value, field_name)


def _validate_index(value: int, field_name: str) -> None:
    _validate_non_negative_int(value, field_name)


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _is_metadata_value(value: object) -> bool:
    return value is None or isinstance(value, (str, int, bool))
