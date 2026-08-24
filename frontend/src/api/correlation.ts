import type { CorrelationDevicesResponse } from "../models/correlation";
import { requestJson } from "./http";
import type { ApiOptions } from "./http";

export { ApiError } from "./http";

export type CorrelationApiOptions = ApiOptions;

export async function getCorrelationDevices(
  options: CorrelationApiOptions = {},
): Promise<CorrelationDevicesResponse> {
  return requestJson<CorrelationDevicesResponse>(
    "/api/v1/correlation/devices",
    options,
  );
}
