export type CorrelationMatchMethod =
  | "exact_of_node"
  | "unmatched"
  | "unavailable";

export type AddressMatchType =
  | "exact"
  | "iomem_contains_dt"
  | "dt_contains_iomem"
  | "overlap"
  | "none"
  | "ambiguous"
  | "unavailable";

export interface CorrelationWarning {
  code: string;
  message: string;
  dt_node_path: string | null;
  runtime_device_path: string | null;
  source_path: string | null;
}

export interface CorrelatedRuntimeDevice {
  name: string;
  sysfs_path: string;
  bus: string;
  driver_name: string | null;
  driver_path: string | null;
  of_node_sysfs_path: string | null;
}

export interface CorrelatedRuntimeDriver {
  name: string;
  sysfs_path: string;
  bus: string;
  module_name: string | null;
}

export interface StaticAddressRegion {
  node_path: string;
  bus_address: string;
  cpu_start: string | null;
  size: string | null;
  cpu_end: string | null;
}

export interface IomemCandidate {
  start: string;
  end: string;
  name: string;
}

export interface AddressCorrelation {
  dt_start: string;
  dt_end: string;
  iomem_start: string | null;
  iomem_end: string | null;
  iomem_name: string | null;
  match_type: AddressMatchType;
  candidates: IomemCandidate[];
}

export interface CorrelatedDevice {
  dt_node_path: string | null;
  runtime_device: CorrelatedRuntimeDevice | null;
  runtime_driver: CorrelatedRuntimeDriver | null;
  static_regions: StaticAddressRegion[];
  address_matches: AddressCorrelation[];
  match_method: CorrelationMatchMethod;
  warnings: CorrelationWarning[];
}

export interface CorrelationDevicesResponse {
  data: CorrelatedDevice[];
  warnings: CorrelationWarning[];
}
