import type { RuntimeMetadataItem } from "./runtime";

export type DependencyKind =
  | "interrupt"
  | "clock"
  | "reset"
  | "power_domain"
  | "dma"
  | "iommu";

export type DependencyEvidenceKind = "declared" | "observed" | "inferred";

export type DependencyResolution =
  | "resolved"
  | "unresolved"
  | "unavailable"
  | "ambiguous";

export type InterruptMatchMethod = "controller_hardware_irq";

export interface DependencyWarning {
  code: string;
  message: string;
  consumer_dt_path: string | null;
  provider_dt_path: string | null;
  runtime_irq: number | null;
  source_path: string | null;
}

export interface DependencyEvidence {
  kind: DependencyEvidenceKind;
  source: string;
  source_path: string | null;
  message: string | null;
}

export interface DependencyRuntimeInterrupt {
  irq: number;
  counts: number[];
  controller: string | null;
  hardware_irq: number | null;
  trigger: string | null;
  actions: string[];
  total_count: number;
  source_path: string;
  metadata: RuntimeMetadataItem[];
}

export interface DeviceDependency {
  kind: DependencyKind;
  consumer_dt_path: string;
  provider_dt_path: string | null;
  provider_phandle: number | null;
  entry_index: number;
  name: string | null;
  specifier_cells: number[];
  source_property: string | null;
  static_resolution: DependencyResolution;
  evidence: DependencyEvidence[];
  interrupt_resolution: DependencyResolution | null;
  interrupt_match_method: InterruptMatchMethod | null;
  runtime_interrupt: DependencyRuntimeInterrupt | null;
  runtime_candidates: DependencyRuntimeInterrupt[];
  interrupt_warnings: DependencyWarning[];
}

export interface DeviceDependencyView {
  dt_node_path: string;
  dependencies: DeviceDependency[];
}

export interface DependencyDevicesResponse {
  data: DeviceDependencyView[];
  warnings: DependencyWarning[];
}
