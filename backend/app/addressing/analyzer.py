from __future__ import annotations

from app.addressing.cell_context import AddressCellContextResolver
from app.addressing.memory_regions import MemoryRegionClassifier
from app.addressing.ranges_translator import (
    RANGES_PROPERTY,
    RangesInterpreter,
    RangesTranslator,
)
from app.addressing.reg_interpreter import REG_PROPERTY, RegInterpreter
from app.model.addressing import (
    AddressingReport,
    AddressingWarning,
    MemoryRegion,
    RangeMapping,
    RegRegion,
    TranslatedAddressRange,
)
from app.model.devicetree import DeviceTree, DeviceTreeNode


class AddressingAnalyzer:
    def __init__(
        self,
        *,
        context_resolver: AddressCellContextResolver | None = None,
        reg_interpreter: RegInterpreter | None = None,
        ranges_interpreter: RangesInterpreter | None = None,
        ranges_translator: RangesTranslator | None = None,
        memory_region_classifier: MemoryRegionClassifier | None = None,
    ) -> None:
        self._context_resolver = context_resolver or AddressCellContextResolver()
        self._reg_interpreter = reg_interpreter or RegInterpreter()
        self._ranges_interpreter = ranges_interpreter or RangesInterpreter()
        self._ranges_translator = ranges_translator or RangesTranslator(
            context_resolver=self._context_resolver,
            ranges_interpreter=self._ranges_interpreter,
        )
        self._memory_region_classifier = (
            memory_region_classifier or MemoryRegionClassifier()
        )

    def analyze(self, tree: DeviceTree) -> AddressingReport:
        mappings: list[RangeMapping] = []
        translations: list[TranslatedAddressRange] = []
        regions: list[MemoryRegion] = []
        warnings: list[AddressingWarning] = []

        for node in tree.iter_nodes():
            if node.get_property(RANGES_PROPERTY) is not None:
                node_mappings, mapping_warnings = self._collect_mappings(node, tree)
                mappings.extend(node_mappings)
                warnings.extend(mapping_warnings)

            if node.get_property(REG_PROPERTY) is None:
                continue

            context, context_warnings = self._context_resolver.resolve(node, tree)
            warnings.extend(context_warnings)

            reg_regions, reg_warnings = self._reg_interpreter.interpret(node, context)
            warnings.extend(reg_warnings)

            for reg_region in reg_regions:
                if _is_sizeless_reg_region(reg_region):
                    warnings.append(_non_memory_reg_semantics_warning(node))
                    continue

                translated = self._ranges_translator.translate(reg_region, node, tree)
                translations.append(translated)

                region, region_warnings = self._memory_region_classifier.classify(
                    translated
                )
                warnings.extend(region_warnings)
                if region is not None:
                    regions.append(region)

        return AddressingReport(
            regions=tuple(regions),
            mappings=tuple(mappings),
            translations=tuple(translations),
            warnings=_deduplicate_warnings(warnings),
        )

    def _collect_mappings(
        self,
        bus_node: DeviceTreeNode,
        tree: DeviceTree,
    ) -> tuple[tuple[RangeMapping, ...], tuple[AddressingWarning, ...]]:
        child_context, child_warnings = self._context_resolver.resolve_for_children(
            bus_node
        )
        parent_context, parent_warnings = self._context_resolver.resolve(bus_node, tree)

        mappings, mapping_warnings = self._ranges_interpreter.interpret(
            bus_node,
            child_context,
            parent_context,
        )

        warnings = child_warnings + parent_warnings + mapping_warnings
        if mappings is None:
            return (), warnings

        return mappings, warnings


def _is_sizeless_reg_region(reg_region: RegRegion) -> bool:
    return reg_region.size is None or reg_region.size == 0


def _non_memory_reg_semantics_warning(node: DeviceTreeNode) -> AddressingWarning:
    return AddressingWarning(
        code="NON_MEMORY_REG_SEMANTICS",
        node_path=node.path,
        message="Size-less reg resource is not treated as an address range",
    )


def _deduplicate_warnings(
    warnings: list[AddressingWarning],
) -> tuple[AddressingWarning, ...]:
    seen: set[tuple[str, str, str]] = set()
    deduplicated: list[AddressingWarning] = []

    for warning in warnings:
        key = (warning.code, warning.node_path, warning.message)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(warning)

    return tuple(deduplicated)
