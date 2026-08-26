import type { DependencyDevicesResponse } from "../models/dependency";
import { requestJson } from "./http";
import type { ApiOptions } from "./http";

export { ApiError } from "./http";

export type DependencyApiOptions = ApiOptions;

export async function getDependencyDevices(
  options: DependencyApiOptions = {},
): Promise<DependencyDevicesResponse> {
  return requestJson<DependencyDevicesResponse>(
    "/api/v1/dependencies/devices",
    options,
  );
}
