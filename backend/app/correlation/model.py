from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.model.addressing import TranslatedAddressRange
from app.runtime.model import RuntimeDevice, RuntimeDriver


class CorrelationMatchMethod(str, Enum):
    EXACT_OF_NODE = "exact_of_node"
    UNMATCHED = "unmatched"


class AddressMatchType(str, Enum):
    EXACT = "exact"
    IOMEM_CONTAINS_DT = "iomem_contains_dt"
    DT_CONTAINS_IOMEM = "dt_contains_iomem"
    OVERLAP = "overlap"
    NONE = "none"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CorrelationWarning:
    code: str
    message: str
    dt_node_path: str | None = None
    runtime_device_path: str | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("CorrelationWarning.code must not be empty")
        if not self.message:
            raise ValueError("CorrelationWarning.message must not be empty")
        _validate_optional_absolute_path(
            self.dt_node_path,
            "CorrelationWarning.dt_node_path",
        )
        _validate_optional_absolute_path(
            self.runtime_device_path,
            "CorrelationWarning.runtime_device_path",
        )


@dataclass(frozen=True)
class IomemCandidate:
    start: int
    end: int
    name: str

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.start, "IomemCandidate.start")
        _validate_non_negative_int(self.end, "IomemCandidate.end")
        if self.end < self.start:
            raise ValueError("IomemCandidate.end must be >= start")
        if not self.name:
            raise ValueError("IomemCandidate.name must not be empty")


@dataclass(frozen=True)
class AddressCorrelation:
    dt_start: int
    dt_end: int
    iomem_start: int | None
    iomem_end: int | None
    iomem_name: str | None
    match_type: AddressMatchType
    candidates: tuple[IomemCandidate, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.dt_start, "AddressCorrelation.dt_start")
        _validate_non_negative_int(self.dt_end, "AddressCorrelation.dt_end")
        if self.dt_end < self.dt_start:
            raise ValueError("AddressCorrelation.dt_end must be >= dt_start")
        if self.iomem_start is not None:
            _validate_non_negative_int(
                self.iomem_start,
                "AddressCorrelation.iomem_start",
            )
        if self.iomem_end is not None:
            _validate_non_negative_int(
                self.iomem_end,
                "AddressCorrelation.iomem_end",
            )
        if self.iomem_start is None and self.iomem_end is not None:
            raise ValueError(
                "AddressCorrelation.iomem_start is required with iomem_end"
            )
        if self.iomem_start is not None and self.iomem_end is None:
            raise ValueError(
                "AddressCorrelation.iomem_end is required with iomem_start"
            )
        if (
            self.iomem_start is not None
            and self.iomem_end is not None
            and self.iomem_end < self.iomem_start
        ):
            raise ValueError("AddressCorrelation.iomem_end must be >= iomem_start")
        if self.iomem_name is not None and not self.iomem_name:
            raise ValueError("AddressCorrelation.iomem_name must not be empty")
        candidates = tuple(self.candidates)
        for candidate in candidates:
            if not isinstance(candidate, IomemCandidate):
                raise TypeError("AddressCorrelation.candidates must be IomemCandidate")
        object.__setattr__(self, "candidates", candidates)
        if not isinstance(self.match_type, AddressMatchType):
            object.__setattr__(
                self,
                "match_type",
                AddressMatchType(self.match_type),
            )


@dataclass(frozen=True)
class CorrelatedDevice:
    dt_node_path: str | None
    runtime_device: RuntimeDevice | None
    runtime_driver: RuntimeDriver | None
    static_regions: tuple[TranslatedAddressRange, ...] = field(default_factory=tuple)
    address_matches: tuple[AddressCorrelation, ...] = field(default_factory=tuple)
    match_method: CorrelationMatchMethod = CorrelationMatchMethod.UNMATCHED
    warnings: tuple[CorrelationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_optional_absolute_path(
            self.dt_node_path,
            "CorrelatedDevice.dt_node_path",
        )
        object.__setattr__(self, "static_regions", tuple(self.static_regions))
        object.__setattr__(self, "address_matches", tuple(self.address_matches))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if not isinstance(self.match_method, CorrelationMatchMethod):
            object.__setattr__(
                self,
                "match_method",
                CorrelationMatchMethod(self.match_method),
            )


@dataclass(frozen=True)
class CorrelationReport:
    devices: tuple[CorrelatedDevice, ...] = field(default_factory=tuple)
    warnings: tuple[CorrelationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "devices", tuple(self.devices))
        object.__setattr__(self, "warnings", tuple(self.warnings))


def _validate_optional_absolute_path(value: str | None, field_name: str) -> None:
    if value is not None and not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
