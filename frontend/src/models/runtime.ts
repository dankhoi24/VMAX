export type RuntimeMetadataValue = string | number | boolean | null;
export type RuntimeMetadataItem = [string, RuntimeMetadataValue];

export interface RuntimeWarning {
  code: string;
  message: string;
  source_path: string | null;
}

export interface RuntimeCollection<T> {
  data: T;
  warnings: RuntimeWarning[];
}

export interface RuntimeSystemInfo {
  hostname: string | null;
  kernel_name: string | null;
  kernel_release: string | null;
  kernel_version: string | null;
  machine: string | null;
  architecture: string | null;
  cmdline: string | null;
}

export interface RuntimeResource {
  index: number;
  start: number;
  end: number;
  flags: number;
  flag_names: string[];
  name: string | null;
  size: number;
}

export interface RuntimeInterrupt {
  irq: number;
  counts: number[];
  controller: string | null;
  hardware_irq: number | null;
  trigger: string | null;
  actions: string[];
  raw_line: string | null;
  source_path: string;
  metadata: RuntimeMetadataItem[];
  total_count: number;
}

export interface RuntimeDevice {
  name: string;
  sysfs_path: string;
  bus: string;
  driver_name: string | null;
  driver_path: string | null;
  of_node_sysfs_path: string | null;
  subsystem_path: string | null;
  modalias: string | null;
  resources: RuntimeResource[];
  metadata: RuntimeMetadataItem[];
}

export interface RuntimeDriver {
  name: string;
  sysfs_path: string;
  bus: string;
  module_name: string | null;
  bound_device_paths: string[];
  metadata: RuntimeMetadataItem[];
}

export interface IomemRegion {
  start: number;
  end: number;
  name: string;
  children: IomemRegion[];
  size: number;
}

export type RuntimeMetadataResponse = RuntimeCollection<RuntimeSystemInfo>;
export type RuntimeDevicesResponse = RuntimeCollection<RuntimeDevice[]>;
export type RuntimeDriversResponse = RuntimeCollection<RuntimeDriver[]>;
export type RuntimeIomemResponse = RuntimeCollection<IomemRegion[]>;
export type RuntimeInterruptsResponse = RuntimeCollection<RuntimeInterrupt[]>;

export function formatHex(value: number): string {
  return `0x${value.toString(16).toUpperCase()}`;
}
