from __future__ import annotations

from pydantic import BaseModel

from app.model.devicetree import PropertyKind


PropertyValueResponse = bool | str | list[str] | list[int] | None


class MetadataResponse(BaseModel):
    filename: str | None
    file_size: int | None
    node_count: int
    property_count: int
    warnings: list[str]
    errors: list[str]


class DeviceTreePropertyResponse(BaseModel):
    name: str
    raw_hex: str
    kind: PropertyKind
    value: PropertyValueResponse


class DeviceTreeNodeResponse(BaseModel):
    id: str
    name: str
    full_name: str
    path: str
    unit_address: str | None
    parent_path: str | None
    properties: list[DeviceTreePropertyResponse]
    children: list["DeviceTreeNodeResponse"]


class DeviceTreeResponse(BaseModel):
    node_count: int
    root: DeviceTreeNodeResponse


class ParseErrorDetail(BaseModel):
    source: str | None
    warnings: list[str]
    errors: list[str]


class ErrorResponse(BaseModel):
    detail: ParseErrorDetail

