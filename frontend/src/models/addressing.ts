export type MemoryRegionKind = "ram" | "reserved" | "device";

export interface AddressingWarning {
  code: string;
  node_path: string;
  message: string;
}

export interface RangeMapping {
  node_path: string;
  index: number;
  child_address: string;
  parent_address: string;
  size: string;
  source_property: string;
}

export interface TranslationStep {
  bus_node_path: string;
  input_address: string;
  output_address: string;
  mapping_index: number | null;
}

export interface TranslatedAddressRange {
  node_path: string;
  bus_address: string;
  cpu_address: string | null;
  size: string | null;
  end: string | null;
  translation_path: TranslationStep[];
  warnings: AddressingWarning[];
}

export interface MemoryRegion {
  node_path: string;
  kind: MemoryRegionKind;
  start: string;
  size: string | null;
  end: string | null;
}

export interface AddressingReport {
  regions: MemoryRegion[];
  mappings: RangeMapping[];
  translations: TranslatedAddressRange[];
  warnings: AddressingWarning[];
}
