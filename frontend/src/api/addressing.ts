import type { AddressingReport } from "../models/addressing";
import { requestJson } from "./http";
import type { ApiOptions } from "./http";

export type AddressingApiOptions = ApiOptions;

export async function getAddressingReport(
  options: AddressingApiOptions = {},
): Promise<AddressingReport> {
  return requestJson<AddressingReport>("/api/v1/addressing", options);
}
