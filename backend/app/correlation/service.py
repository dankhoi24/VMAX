from __future__ import annotations

from app.correlation.model import (
    AddressCorrelation,
    AddressMatchType,
    CorrelatedDevice,
    CorrelationMatchMethod,
    CorrelationReport,
    CorrelationWarning,
    IomemCandidate,
)
from app.model.addressing import AddressingReport, TranslatedAddressRange
from app.model.devicetree import DeviceTree
from app.runtime.model import IomemRegion, RuntimeDevice, RuntimeDriver


DEVICE_TREE_SYSFS_BASE = "/sys/firmware/devicetree/base"


class OfNodePathNormalizer:
    def normalize(self, of_node_sysfs_path: str) -> str | None:
        path = of_node_sysfs_path.rstrip("/")
        if path == DEVICE_TREE_SYSFS_BASE:
            return "/"
        prefix = f"{DEVICE_TREE_SYSFS_BASE}/"
        if not path.startswith(prefix):
            return None

        relative_path = path[len(prefix):].strip("/")
        if not relative_path:
            return "/"
        return f"/{relative_path}"


class CorrelationService:
    def __init__(
        self,
        of_node_normalizer: OfNodePathNormalizer | None = None,
    ) -> None:
        self._of_node_normalizer = of_node_normalizer or OfNodePathNormalizer()

    def correlate(
        self,
        *,
        tree: DeviceTree,
        addressing: AddressingReport,
        devices: tuple[RuntimeDevice, ...],
        drivers: tuple[RuntimeDriver, ...],
        iomem: tuple[IomemRegion, ...],
    ) -> CorrelationReport:
        warnings: list[CorrelationWarning] = []
        drivers_by_path = {driver.sysfs_path: driver for driver in drivers}
        drivers_by_name = {driver.name: driver for driver in drivers}
        translations_by_node = _group_translations_by_node(addressing.translations)
        iomem_regions = tuple(_iter_iomem_regions(iomem))

        correlated_devices: list[CorrelatedDevice] = []
        matched_dt_paths: set[str] = set()

        for device in devices:
            correlated = self._correlate_runtime_device(
                tree=tree,
                device=device,
                drivers_by_path=drivers_by_path,
                drivers_by_name=drivers_by_name,
                translations_by_node=translations_by_node,
                iomem_regions=iomem_regions,
            )
            correlated_devices.append(correlated)
            warnings.extend(correlated.warnings)
            if correlated.dt_node_path is not None:
                matched_dt_paths.add(correlated.dt_node_path)

        for node_path in sorted(translations_by_node):
            if node_path in matched_dt_paths:
                continue
            if tree.get_node(node_path) is None:
                continue

            node_translations = translations_by_node[node_path]
            node_warnings: list[CorrelationWarning] = []
            correlated = CorrelatedDevice(
                dt_node_path=node_path,
                runtime_device=None,
                runtime_driver=None,
                static_regions=node_translations,
                address_matches=self._correlate_addresses(
                    node_translations,
                    iomem_regions,
                    warnings=node_warnings,
                ),
                match_method=CorrelationMatchMethod.UNMATCHED,
                warnings=tuple(node_warnings),
            )
            correlated_devices.append(correlated)
            warnings.extend(correlated.warnings)

        return CorrelationReport(
            devices=tuple(correlated_devices),
            warnings=tuple(warnings),
        )

    def _correlate_runtime_device(
        self,
        *,
        tree: DeviceTree,
        device: RuntimeDevice,
        drivers_by_path: dict[str, RuntimeDriver],
        drivers_by_name: dict[str, RuntimeDriver],
        translations_by_node: dict[str, tuple[TranslatedAddressRange, ...]],
        iomem_regions: tuple[IomemRegion, ...],
    ) -> CorrelatedDevice:
        warnings: list[CorrelationWarning] = []
        dt_node_path = self._normalize_device_of_node(device, warnings)
        if dt_node_path is not None and tree.get_node(dt_node_path) is None:
            warnings.append(
                CorrelationWarning(
                    code="OF_NODE_DT_NODE_NOT_FOUND",
                    runtime_device_path=device.sysfs_path,
                    dt_node_path=dt_node_path,
                    message=(
                        "Runtime device of_node points to a Device Tree path "
                        "that is not present in the parsed DTB"
                    ),
                )
            )
            dt_node_path = None

        runtime_driver = _find_runtime_driver(
            device,
            drivers_by_path=drivers_by_path,
            drivers_by_name=drivers_by_name,
            warnings=warnings,
        )
        static_regions = (
            translations_by_node.get(dt_node_path, ())
            if dt_node_path is not None
            else ()
        )
        address_matches = self._correlate_addresses(
            static_regions,
            iomem_regions,
            warnings=warnings,
        )

        return CorrelatedDevice(
            dt_node_path=dt_node_path,
            runtime_device=device,
            runtime_driver=runtime_driver,
            static_regions=static_regions,
            address_matches=address_matches,
            match_method=(
                CorrelationMatchMethod.EXACT_OF_NODE
                if dt_node_path is not None
                else CorrelationMatchMethod.UNMATCHED
            ),
            warnings=tuple(warnings),
        )

    def _normalize_device_of_node(
        self,
        device: RuntimeDevice,
        warnings: list[CorrelationWarning],
    ) -> str | None:
        if device.of_node_sysfs_path is None:
            return None

        dt_node_path = self._of_node_normalizer.normalize(device.of_node_sysfs_path)
        if dt_node_path is not None:
            return dt_node_path

        warnings.append(
            CorrelationWarning(
                code="OF_NODE_PATH_UNSUPPORTED",
                runtime_device_path=device.sysfs_path,
                message=(
                    "Runtime device of_node path is outside "
                    f"{DEVICE_TREE_SYSFS_BASE}"
                ),
            )
        )
        return None

    def _correlate_addresses(
        self,
        static_regions: tuple[TranslatedAddressRange, ...],
        iomem_regions: tuple[IomemRegion, ...],
        warnings: list[CorrelationWarning],
    ) -> tuple[AddressCorrelation, ...]:
        matches: list[AddressCorrelation] = []

        for region in static_regions:
            if region.cpu_address is None or region.end is None:
                warnings.append(
                    CorrelationWarning(
                        code="DT_REGION_UNRESOLVED",
                        dt_node_path=region.node_path,
                        message=(
                            "DT translated address region has no resolved "
                            "CPU-visible range"
                        ),
                    )
                )
                continue

            matches.append(
                _match_region_to_iomem(
                    node_path=region.node_path,
                    dt_start=region.cpu_address,
                    dt_end=region.end,
                    iomem_regions=iomem_regions,
                    warnings=warnings,
                )
            )

        return tuple(matches)


def _find_runtime_driver(
    device: RuntimeDevice,
    *,
    drivers_by_path: dict[str, RuntimeDriver],
    drivers_by_name: dict[str, RuntimeDriver],
    warnings: list[CorrelationWarning],
) -> RuntimeDriver | None:
    if device.driver_path is not None:
        driver = drivers_by_path.get(device.driver_path)
        if driver is not None:
            return driver

    if device.driver_name is not None:
        driver = drivers_by_name.get(device.driver_name)
        if driver is not None:
            return driver

    if device.driver_name is not None or device.driver_path is not None:
        warnings.append(
            CorrelationWarning(
                code="RUNTIME_DRIVER_NOT_FOUND",
                runtime_device_path=device.sysfs_path,
                message="Runtime device reports a driver that is not in RuntimeDriver[]",
            )
        )

    return None


def _group_translations_by_node(
    translations: tuple[TranslatedAddressRange, ...],
) -> dict[str, tuple[TranslatedAddressRange, ...]]:
    grouped: dict[str, list[TranslatedAddressRange]] = {}
    for translation in translations:
        grouped.setdefault(translation.node_path, []).append(translation)
    return {node_path: tuple(values) for node_path, values in grouped.items()}


def _iter_iomem_regions(
    regions: tuple[IomemRegion, ...],
) -> tuple[IomemRegion, ...]:
    flattened: list[IomemRegion] = []
    for region in regions:
        flattened.append(region)
        flattened.extend(_iter_iomem_regions(region.children))
    return tuple(flattened)


def _match_region_to_iomem(
    *,
    node_path: str,
    dt_start: int,
    dt_end: int,
    iomem_regions: tuple[IomemRegion, ...],
    warnings: list[CorrelationWarning],
) -> AddressCorrelation:
    exact = [
        region
        for region in iomem_regions
        if region.start == dt_start and region.end == dt_end
    ]
    if exact:
        return _single_or_ambiguous(
            node_path=node_path,
            dt_start=dt_start,
            dt_end=dt_end,
            candidates=tuple(exact),
            match_type=AddressMatchType.EXACT,
            warnings=warnings,
        )

    iomem_contains_dt = [
        region
        for region in iomem_regions
        if _contains(region.start, region.end, dt_start, dt_end)
    ]
    if iomem_contains_dt:
        return _single_or_ambiguous(
            node_path=node_path,
            dt_start=dt_start,
            dt_end=dt_end,
            candidates=tuple(iomem_contains_dt),
            match_type=AddressMatchType.IOMEM_CONTAINS_DT,
            warnings=warnings,
        )

    dt_contains_iomem = [
        region
        for region in iomem_regions
        if _contains(dt_start, dt_end, region.start, region.end)
    ]
    if dt_contains_iomem:
        return _single_or_ambiguous(
            node_path=node_path,
            dt_start=dt_start,
            dt_end=dt_end,
            candidates=tuple(dt_contains_iomem),
            match_type=AddressMatchType.DT_CONTAINS_IOMEM,
            warnings=warnings,
        )

    overlaps = [
        region
        for region in iomem_regions
        if _overlaps(region.start, region.end, dt_start, dt_end)
    ]
    if overlaps:
        return _single_or_ambiguous(
            node_path=node_path,
            dt_start=dt_start,
            dt_end=dt_end,
            candidates=tuple(overlaps),
            match_type=AddressMatchType.OVERLAP,
            warnings=warnings,
        )

    return AddressCorrelation(
        dt_start=dt_start,
        dt_end=dt_end,
        iomem_start=None,
        iomem_end=None,
        iomem_name=None,
        match_type=AddressMatchType.NONE,
    )


def _single_or_ambiguous(
    *,
    node_path: str,
    dt_start: int,
    dt_end: int,
    candidates: tuple[IomemRegion, ...],
    match_type: AddressMatchType,
    warnings: list[CorrelationWarning],
) -> AddressCorrelation:
    iomem_candidates = tuple(_iomem_candidate(region) for region in candidates)
    if len(candidates) > 1:
        warnings.append(
            CorrelationWarning(
                code="ADDRESS_MATCH_AMBIGUOUS",
                dt_node_path=node_path,
                message=(
                    "DT translated region matches multiple /proc/iomem "
                    f"regions with match type {match_type.value}"
                ),
            )
        )
        return AddressCorrelation(
            dt_start=dt_start,
            dt_end=dt_end,
            iomem_start=None,
            iomem_end=None,
            iomem_name=None,
            match_type=AddressMatchType.AMBIGUOUS,
            candidates=iomem_candidates,
        )

    candidate = candidates[0]
    return AddressCorrelation(
        dt_start=dt_start,
        dt_end=dt_end,
        iomem_start=candidate.start,
        iomem_end=candidate.end,
        iomem_name=candidate.name,
        match_type=match_type,
        candidates=iomem_candidates,
    )


def _iomem_candidate(region: IomemRegion) -> IomemCandidate:
    return IomemCandidate(
        start=region.start,
        end=region.end,
        name=region.name,
    )


def _contains(start: int, end: int, child_start: int, child_end: int) -> bool:
    return start <= child_start and end >= child_end


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end
