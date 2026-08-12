from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MemoryRegionKind(str, Enum):
    RAM = "ram"
    RESERVED = "reserved"
    DEVICE = "device"


@dataclass(frozen=True)
class AddressingWarning:
    code: str
    node_path: str
    message: str

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("AddressingWarning.code must not be empty")
        if not self.node_path.startswith("/"):
            raise ValueError("AddressingWarning.node_path must be absolute")
        if not self.message:
            raise ValueError("AddressingWarning.message must not be empty")


@dataclass(frozen=True)
class AddressCellContext:
    address_cells: int
    size_cells: int
    source_node_path: str
    used_default_address_cells: bool = False
    used_default_size_cells: bool = False

    def __post_init__(self) -> None:
        if self.address_cells < 0:
            raise ValueError("AddressCellContext.address_cells must be >= 0")
        if self.size_cells < 0:
            raise ValueError("AddressCellContext.size_cells must be >= 0")
        if not self.source_node_path.startswith("/"):
            raise ValueError("AddressCellContext.source_node_path must be absolute")


@dataclass(frozen=True)
class RegRegion:
    node_path: str
    index: int
    bus_address: int
    size: int | None
    source_property: str = "reg"

    def __post_init__(self) -> None:
        _validate_node_path(self.node_path, "RegRegion.node_path")
        _validate_index(self.index, "RegRegion.index")
        _validate_non_negative_int(self.bus_address, "RegRegion.bus_address")
        if self.size is not None:
            _validate_non_negative_int(self.size, "RegRegion.size")
        if not self.source_property:
            raise ValueError("RegRegion.source_property must not be empty")

    @property
    def end(self) -> int | None:
        if self.size is None or self.size == 0:
            return None
        return self.bus_address + self.size - 1


@dataclass(frozen=True)
class RangeMapping:
    node_path: str
    index: int
    child_address: int
    parent_address: int
    size: int
    source_property: str = "ranges"

    def __post_init__(self) -> None:
        _validate_node_path(self.node_path, "RangeMapping.node_path")
        _validate_index(self.index, "RangeMapping.index")
        _validate_non_negative_int(self.child_address, "RangeMapping.child_address")
        _validate_non_negative_int(self.parent_address, "RangeMapping.parent_address")
        _validate_non_negative_int(self.size, "RangeMapping.size")
        if not self.source_property:
            raise ValueError("RangeMapping.source_property must not be empty")


@dataclass(frozen=True)
class TranslationStep:
    bus_node_path: str
    input_address: int
    output_address: int
    mapping_index: int | None

    def __post_init__(self) -> None:
        _validate_node_path(self.bus_node_path, "TranslationStep.bus_node_path")
        _validate_non_negative_int(self.input_address, "TranslationStep.input_address")
        _validate_non_negative_int(self.output_address, "TranslationStep.output_address")
        if self.mapping_index is not None:
            _validate_index(self.mapping_index, "TranslationStep.mapping_index")


@dataclass(frozen=True)
class TranslatedAddressRange:
    node_path: str
    bus_address: int
    cpu_address: int | None
    size: int | None
    translation_path: tuple[TranslationStep, ...] = field(default_factory=tuple)
    warnings: tuple[AddressingWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_node_path(self.node_path, "TranslatedAddressRange.node_path")
        _validate_non_negative_int(self.bus_address, "TranslatedAddressRange.bus_address")
        if self.cpu_address is not None:
            _validate_non_negative_int(
                self.cpu_address,
                "TranslatedAddressRange.cpu_address",
            )
        if self.size is not None:
            _validate_non_negative_int(self.size, "TranslatedAddressRange.size")
        object.__setattr__(self, "translation_path", tuple(self.translation_path))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    @property
    def end(self) -> int | None:
        if self.cpu_address is None or self.size is None or self.size == 0:
            return None
        return self.cpu_address + self.size - 1


@dataclass(frozen=True)
class MemoryRegion:
    node_path: str
    kind: MemoryRegionKind
    start: int
    size: int | None

    def __post_init__(self) -> None:
        _validate_node_path(self.node_path, "MemoryRegion.node_path")
        if not isinstance(self.kind, MemoryRegionKind):
            object.__setattr__(self, "kind", MemoryRegionKind(self.kind))
        _validate_non_negative_int(self.start, "MemoryRegion.start")
        if self.size is not None:
            _validate_non_negative_int(self.size, "MemoryRegion.size")

    @property
    def end(self) -> int | None:
        if self.size is None or self.size == 0:
            return None
        return self.start + self.size - 1


@dataclass(frozen=True)
class AddressingReport:
    regions: tuple[MemoryRegion, ...] = field(default_factory=tuple)
    mappings: tuple[RangeMapping, ...] = field(default_factory=tuple)
    translations: tuple[TranslatedAddressRange, ...] = field(default_factory=tuple)
    warnings: tuple[AddressingWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regions", tuple(self.regions))
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "translations", tuple(self.translations))
        object.__setattr__(self, "warnings", tuple(self.warnings))


def _validate_node_path(value: str, field_name: str) -> None:
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_index(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
