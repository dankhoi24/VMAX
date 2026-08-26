from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.dependency.model import DependencyReference
from app.runtime.model import MetadataItems, RuntimeInterrupt


class InterruptCorrelationResolution(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class InterruptMatchMethod(str, Enum):
    CONTROLLER_HARDWARE_IRQ = "controller_hardware_irq"


@dataclass(frozen=True)
class InterruptCorrelationWarning:
    code: str
    message: str
    consumer_dt_path: str | None = None
    provider_dt_path: str | None = None
    runtime_irq: int | None = None
    source_path: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.code, "InterruptCorrelationWarning.code")
        _validate_non_empty(self.message, "InterruptCorrelationWarning.message")
        _validate_optional_absolute_path(
            self.consumer_dt_path,
            "InterruptCorrelationWarning.consumer_dt_path",
        )
        _validate_optional_absolute_path(
            self.provider_dt_path,
            "InterruptCorrelationWarning.provider_dt_path",
        )
        if self.runtime_irq is not None:
            _validate_non_negative_int(
                self.runtime_irq,
                "InterruptCorrelationWarning.runtime_irq",
            )
        _validate_optional_absolute_path(
            self.source_path,
            "InterruptCorrelationWarning.source_path",
        )


@dataclass(frozen=True)
class InterruptIdentity:
    controller_key: str
    hardware_irq: int
    trigger: str | None = None
    source: str = "unknown"
    source_path: str | None = None
    metadata: MetadataItems = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty(self.controller_key, "InterruptIdentity.controller_key")
        _validate_non_negative_int(self.hardware_irq, "InterruptIdentity.hardware_irq")
        _validate_optional_non_empty(self.trigger, "InterruptIdentity.trigger")
        _validate_non_empty(self.source, "InterruptIdentity.source")
        _validate_optional_absolute_path(
            self.source_path,
            "InterruptIdentity.source_path",
        )
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))


@dataclass(frozen=True)
class InterruptCorrelation:
    dependency: DependencyReference
    dt_identities: tuple[InterruptIdentity, ...] = field(default_factory=tuple)
    runtime_interrupt: RuntimeInterrupt | None = None
    runtime_candidates: tuple[RuntimeInterrupt, ...] = field(default_factory=tuple)
    resolution: InterruptCorrelationResolution = (
        InterruptCorrelationResolution.UNRESOLVED
    )
    match_method: InterruptMatchMethod | None = None
    warnings: tuple[InterruptCorrelationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.dependency, DependencyReference):
            raise TypeError("InterruptCorrelation.dependency must be DependencyReference")
        object.__setattr__(
            self,
            "dt_identities",
            _normalize_identity_tuple(self.dt_identities),
        )
        runtime_candidates = tuple(self.runtime_candidates)
        for interrupt in runtime_candidates:
            if not isinstance(interrupt, RuntimeInterrupt):
                raise TypeError(
                    "InterruptCorrelation.runtime_candidates must be RuntimeInterrupt"
                )
        object.__setattr__(self, "runtime_candidates", runtime_candidates)
        if self.runtime_interrupt is not None and not isinstance(
            self.runtime_interrupt,
            RuntimeInterrupt,
        ):
            raise TypeError(
                "InterruptCorrelation.runtime_interrupt must be RuntimeInterrupt"
            )
        if not isinstance(self.resolution, InterruptCorrelationResolution):
            object.__setattr__(
                self,
                "resolution",
                InterruptCorrelationResolution(self.resolution),
            )
        if self.match_method is not None and not isinstance(
            self.match_method,
            InterruptMatchMethod,
        ):
            object.__setattr__(
                self,
                "match_method",
                InterruptMatchMethod(self.match_method),
            )
        warnings = tuple(self.warnings)
        for warning in warnings:
            if not isinstance(warning, InterruptCorrelationWarning):
                raise TypeError(
                    "InterruptCorrelation.warnings must be InterruptCorrelationWarning"
                )
        object.__setattr__(self, "warnings", warnings)


@dataclass(frozen=True)
class InterruptCorrelationReport:
    correlations: tuple[InterruptCorrelation, ...] = field(default_factory=tuple)
    warnings: tuple[InterruptCorrelationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        correlations = tuple(self.correlations)
        for correlation in correlations:
            if not isinstance(correlation, InterruptCorrelation):
                raise TypeError(
                    "InterruptCorrelationReport.correlations must be "
                    "InterruptCorrelation"
                )
        warnings = tuple(self.warnings)
        for warning in warnings:
            if not isinstance(warning, InterruptCorrelationWarning):
                raise TypeError(
                    "InterruptCorrelationReport.warnings must be "
                    "InterruptCorrelationWarning"
                )
        object.__setattr__(self, "correlations", correlations)
        object.__setattr__(self, "warnings", warnings)


def _normalize_identity_tuple(
    value: tuple[InterruptIdentity, ...],
) -> tuple[InterruptIdentity, ...]:
    identities = tuple(value)
    for identity in identities:
        if not isinstance(identity, InterruptIdentity):
            raise TypeError("InterruptCorrelation.dt_identities must be InterruptIdentity")
    return identities


def _normalize_metadata(value: MetadataItems) -> MetadataItems:
    items: list[tuple[str, str | int | bool | None]] = []
    for key, item_value in value:
        _validate_non_empty(key, "metadata key")
        if item_value is not None and not isinstance(item_value, (str, int, bool)):
            raise TypeError("metadata value must be str, int, bool, or None")
        items.append((key, item_value))
    return tuple(items)


def _validate_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must not be empty")


def _validate_optional_non_empty(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_non_empty(value, field_name)


def _validate_optional_absolute_path(value: str | None, field_name: str) -> None:
    if value is not None and not value.startswith("/"):
        raise ValueError(f"{field_name} must be absolute")


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
