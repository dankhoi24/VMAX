from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DependencyKind(str, Enum):
    INTERRUPT = "interrupt"
    CLOCK = "clock"
    RESET = "reset"
    POWER_DOMAIN = "power_domain"
    DMA = "dma"
    IOMMU = "iommu"


class DependencyEvidenceKind(str, Enum):
    DECLARED = "declared"
    OBSERVED = "observed"
    INFERRED = "inferred"


class DependencyResolution(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class DependencyEvidence:
    kind: DependencyEvidenceKind
    source: str
    source_path: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DependencyEvidenceKind):
            object.__setattr__(self, "kind", DependencyEvidenceKind(self.kind))
        _validate_non_empty(self.source, "DependencyEvidence.source")
        _validate_optional_absolute_path(
            self.source_path,
            "DependencyEvidence.source_path",
        )
        _validate_optional_non_empty(self.message, "DependencyEvidence.message")


@dataclass(frozen=True)
class DependencyReference:
    kind: DependencyKind
    consumer_dt_path: str
    provider_dt_path: str | None
    entry_index: int = 0
    provider_phandle: int | None = None
    name: str | None = None
    specifier_cells: tuple[int, ...] = field(default_factory=tuple)
    source_property: str | None = None
    resolution: DependencyResolution = DependencyResolution.RESOLVED
    evidence: tuple[DependencyEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DependencyKind):
            object.__setattr__(self, "kind", DependencyKind(self.kind))
        if not isinstance(self.resolution, DependencyResolution):
            object.__setattr__(
                self,
                "resolution",
                DependencyResolution(self.resolution),
            )
        _validate_absolute_path(
            self.consumer_dt_path,
            "DependencyReference.consumer_dt_path",
        )
        _validate_optional_absolute_path(
            self.provider_dt_path,
            "DependencyReference.provider_dt_path",
        )
        _validate_index(self.entry_index, "DependencyReference.entry_index")
        if self.provider_phandle is not None:
            _validate_uint32_cell(
                self.provider_phandle,
                "DependencyReference.provider_phandle",
            )
        _validate_optional_non_empty(self.name, "DependencyReference.name")
        _validate_optional_non_empty(
            self.source_property,
            "DependencyReference.source_property",
        )
        object.__setattr__(
            self,
            "specifier_cells",
            _normalize_cell_tuple(self.specifier_cells),
        )
        evidence = tuple(self.evidence)
        for item in evidence:
            if not isinstance(item, DependencyEvidence):
                raise TypeError(
                    "DependencyReference.evidence must be DependencyEvidence"
                )
        object.__setattr__(self, "evidence", evidence)
        if (
            self.resolution == DependencyResolution.RESOLVED
            and self.provider_dt_path is None
        ):
            raise ValueError(
                "DependencyReference.provider_dt_path is required when resolved"
            )


def _validate_index(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")


def _normalize_cell_tuple(value: tuple[int, ...]) -> tuple[int, ...]:
    cells = tuple(value)
    for cell in cells:
        _validate_uint32_cell(cell, "DependencyReference.specifier_cells")
    return cells


def _validate_uint32_cell(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must contain int cells")
    if value < 0:
        raise ValueError(f"{field_name} must contain cells >= 0")
    if value > 0xFFFF_FFFF:
        raise ValueError(f"{field_name} must contain 32-bit cells")


def _validate_absolute_path(value: str, field_name: str) -> None:
    if not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_optional_absolute_path(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_absolute_path(value, field_name)


def _validate_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _validate_optional_non_empty(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_non_empty(value, field_name)
