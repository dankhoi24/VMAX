export type PropertyKind =
  | "boolean"
  | "string"
  | "string_list"
  | "cells"
  | "bytes"
  | "unknown";

export type PropertyValue = boolean | string | string[] | number[] | null;

export interface MetadataResponse {
  filename: string | null;
  file_size: number | null;
  node_count: number;
  property_count: number;
  warnings: string[];
  errors: string[];
}

export interface DeviceTreeProperty {
  name: string;
  raw_hex: string;
  kind: PropertyKind;
  value: PropertyValue;
}

export interface DeviceTreeNode {
  id: string;
  name: string;
  full_name: string;
  path: string;
  unit_address: string | null;
  parent_path: string | null;
  properties: DeviceTreeProperty[];
  children: DeviceTreeNode[];
}

export interface DeviceTreeResponse {
  node_count: number;
  root: DeviceTreeNode;
}

export interface ParseErrorDetail {
  source: string | null;
  warnings: string[];
  errors: string[];
}

export interface ErrorResponse {
  detail: ParseErrorDetail;
}
