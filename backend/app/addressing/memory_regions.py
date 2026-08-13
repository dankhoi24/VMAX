from __future__ import annotations

from collections.abc import Iterable

from app.model.addressing import (
    AddressingWarning,
    MemoryRegion,
    MemoryRegionKind,
    TranslatedAddressRange,
)


RESERVED_MEMORY_PATH = "/reserved-memory"


class MemoryRegionClassifier:
    def classify(
        self,
        translated_range: TranslatedAddressRange,
    ) -> tuple[MemoryRegion | None, tuple[AddressingWarning, ...]]:
        warnings = list(translated_range.warnings)

        if translated_range.cpu_address is None:
            warnings.append(
                AddressingWarning(
                    code="MEMORY_REGION_TRANSLATION_UNRESOLVED",
                    node_path=translated_range.node_path,
                    message=(
                        "Cannot classify memory region without a translated "
                        "CPU-visible address"
                    ),
                )
            )
            return None, tuple(warnings)

        kind, unsupported_warning = _classify_kind(translated_range.node_path)
        if unsupported_warning is not None:
            warnings.append(unsupported_warning)
            return None, tuple(warnings)

        return (
            MemoryRegion(
                node_path=translated_range.node_path,
                kind=kind,
                start=translated_range.cpu_address,
                size=translated_range.size,
            ),
            tuple(warnings),
        )

    def classify_many(
        self,
        translated_ranges: Iterable[TranslatedAddressRange],
    ) -> tuple[tuple[MemoryRegion, ...], tuple[AddressingWarning, ...]]:
        regions: list[MemoryRegion] = []
        warnings: list[AddressingWarning] = []

        for translated_range in translated_ranges:
            region, region_warnings = self.classify(translated_range)
            warnings.extend(region_warnings)
            if region is not None:
                regions.append(region)

        return tuple(regions), tuple(warnings)


def _classify_kind(
    node_path: str,
) -> tuple[MemoryRegionKind, AddressingWarning | None]:
    if _is_root_memory_node(node_path):
        return MemoryRegionKind.RAM, None

    if _is_reserved_memory_region_node(node_path):
        return MemoryRegionKind.RESERVED, None

    if node_path in ("/", RESERVED_MEMORY_PATH):
        return MemoryRegionKind.DEVICE, AddressingWarning(
            code="UNSUPPORTED_MEMORY_REGION_NODE",
            node_path=node_path,
            message=f"Node {node_path} is a container, not a memory region resource",
        )

    return MemoryRegionKind.DEVICE, None


def _is_root_memory_node(node_path: str) -> bool:
    segments = [segment for segment in node_path.split("/") if segment]
    if len(segments) != 1:
        return False

    segment = segments[0]
    return segment == "memory" or segment.startswith("memory@")


def _is_reserved_memory_region_node(node_path: str) -> bool:
    prefix = f"{RESERVED_MEMORY_PATH}/"
    if not node_path.startswith(prefix):
        return False

    remainder = node_path[len(prefix) :]
    return bool(remainder) and "/" not in remainder
