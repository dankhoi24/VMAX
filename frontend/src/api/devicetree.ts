import type {
  DeviceTreeResponse,
  ErrorResponse,
  MetadataResponse,
} from "../models/devicetree";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ErrorResponse["detail"] | null;

  constructor(
    message: string,
    status: number,
    detail: ErrorResponse["detail"] | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface DeviceTreeApiOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

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

async function requestJson<T>(
  path: string,
  options: DeviceTreeApiOptions,
): Promise<T> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const response = await fetchImpl(buildUrl(options.baseUrl, path), {
    headers: {
      Accept: "application/json",
    },
  });

  const body = await readJson(response);
  if (!response.ok) {
    const errorBody = isErrorResponse(body) ? body : null;
    throw new ApiError(
      errorBody?.detail.errors.join("; ") || response.statusText,
      response.status,
      errorBody?.detail ?? null,
    );
  }

  return body as T;
}

function buildUrl(baseUrl: string | undefined, path: string): string {
  if (!baseUrl) {
    return path;
  }

  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  return JSON.parse(text);
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object" || !("detail" in value)) {
    return false;
  }

  const detail = (value as { detail: unknown }).detail;
  return (
    !!detail &&
    typeof detail === "object" &&
    Array.isArray((detail as { errors?: unknown }).errors)
  );
}
