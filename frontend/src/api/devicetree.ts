import type {
  DeviceTreeResponse,
  MetadataResponse,
} from "../models/devicetree";
import { requestJson } from "./http";
import type { ApiOptions } from "./http";

export { ApiError } from "./http";

export type DeviceTreeApiOptions = ApiOptions;

export async function getMetadata(
  options: DeviceTreeApiOptions = {},
): Promise<MetadataResponse> {
  return requestJson<MetadataResponse>("/api/v1/metadata", options);
}

export async function getDeviceTree(
  options: DeviceTreeApiOptions = {},
): Promise<DeviceTreeResponse> {
  return requestJson<DeviceTreeResponse>("/api/v1/devicetree", options);
}
