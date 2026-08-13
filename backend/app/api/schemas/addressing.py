from __future__ import annotations

from pydantic import BaseModel

from app.model.addressing import (
    AddressingReport,
    AddressingWarning,
    MemoryRegion,
    MemoryRegionKind,
    RangeMapping,
    TranslatedAddressRange,
    TranslationStep,
)


class AddressingWarningResponse(BaseModel):
    code: str
    node_path: str
    message: str


class RangeMappingResponse(BaseModel):
    node_path: str
    index: int
    child_address: str
    parent_address: str
    size: str
    source_property: str


class TranslationStepResponse(BaseModel):
    bus_node_path: str
    input_address: str
    output_address: str
    mapping_index: int | None


class TranslatedAddressRangeResponse(BaseModel):
    node_path: str
    bus_address: str
    cpu_address: str | None
    size: str | None
    end: str | None
    translation_path: list[TranslationStepResponse]
    warnings: list[AddressingWarningResponse]


class MemoryRegionResponse(BaseModel):
    node_path: str
    kind: MemoryRegionKind
    start: str
    size: str | None
    end: str | None


class AddressingReportResponse(BaseModel):
    regions: list[MemoryRegionResponse]
    mappings: list[RangeMappingResponse]
    translations: list[TranslatedAddressRangeResponse]
    warnings: list[AddressingWarningResponse]


def addressing_report_to_response(report: AddressingReport) -> AddressingReportResponse:
    return AddressingReportResponse(
        regions=[_memory_region_to_response(region) for region in report.regions],
        mappings=[_range_mapping_to_response(mapping) for mapping in report.mappings],
        translations=[
            _translated_range_to_response(translation)
            for translation in report.translations
        ],
        warnings=[_warning_to_response(warning) for warning in report.warnings],
    )


def _memory_region_to_response(region: MemoryRegion) -> MemoryRegionResponse:
    return MemoryRegionResponse(
        node_path=region.node_path,
        kind=region.kind,
        start=_hex(region.start),
        size=_hex(region.size),
        end=_hex(region.end),
    )


def _range_mapping_to_response(mapping: RangeMapping) -> RangeMappingResponse:
    return RangeMappingResponse(
        node_path=mapping.node_path,
        index=mapping.index,
        child_address=_hex(mapping.child_address),
        parent_address=_hex(mapping.parent_address),
        size=_hex(mapping.size),
        source_property=mapping.source_property,
    )


def _translated_range_to_response(
    translated_range: TranslatedAddressRange,
) -> TranslatedAddressRangeResponse:
    return TranslatedAddressRangeResponse(
        node_path=translated_range.node_path,
        bus_address=_hex(translated_range.bus_address),
        cpu_address=_hex(translated_range.cpu_address),
        size=_hex(translated_range.size),
        end=_hex(translated_range.end),
        translation_path=[
            _translation_step_to_response(step)
            for step in translated_range.translation_path
        ],
        warnings=[
            _warning_to_response(warning)
            for warning in translated_range.warnings
        ],
    )


def _translation_step_to_response(step: TranslationStep) -> TranslationStepResponse:
    return TranslationStepResponse(
        bus_node_path=step.bus_node_path,
        input_address=_hex(step.input_address),
        output_address=_hex(step.output_address),
        mapping_index=step.mapping_index,
    )


def _warning_to_response(warning: AddressingWarning) -> AddressingWarningResponse:
    return AddressingWarningResponse(
        code=warning.code,
        node_path=warning.node_path,
        message=warning.message,
    )


def _hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:x}"
