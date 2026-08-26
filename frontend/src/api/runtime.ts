import type {
  RuntimeDevicesResponse,
  RuntimeDriversResponse,
  RuntimeIomemResponse,
  RuntimeInterruptsResponse,
  RuntimeMetadataResponse,
} from "../models/runtime";
import { requestJson } from "./http";
import type { ApiOptions } from "./http";

export { ApiError } from "./http";

export type RuntimeApiOptions = ApiOptions;

export async function getRuntimeMetadata(
  options: RuntimeApiOptions = {},
): Promise<RuntimeMetadataResponse> {
  return requestJson<RuntimeMetadataResponse>(
    "/api/v1/runtime/metadata",
    options,
  );
}

export async function getRuntimeDevices(
  options: RuntimeApiOptions = {},
): Promise<RuntimeDevicesResponse> {
  return requestJson<RuntimeDevicesResponse>(
    "/api/v1/runtime/devices",
    options,
  );
}

export async function getRuntimeDrivers(
  options: RuntimeApiOptions = {},
): Promise<RuntimeDriversResponse> {
  return requestJson<RuntimeDriversResponse>(
    "/api/v1/runtime/drivers",
    options,
  );
}

export async function getRuntimeIomem(
  options: RuntimeApiOptions = {},
): Promise<RuntimeIomemResponse> {
  return requestJson<RuntimeIomemResponse>("/api/v1/runtime/iomem", options);
}

export async function getRuntimeInterrupts(
  options: RuntimeApiOptions = {},
): Promise<RuntimeInterruptsResponse> {
  return requestJson<RuntimeInterruptsResponse>(
    "/api/v1/runtime/interrupts",
    options,
  );
}
