import { describe, expect, it } from "vitest";

import {
  ApiError,
  getDeviceTree,
  getMetadata,
} from "./devicetree";
import type {
  DeviceTreeResponse,
  ErrorResponse,
  MetadataResponse,
} from "../models/devicetree";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
    ...init,
  });
}

function textResponse(body: string, init: ResponseInit = {}): Response {
  return new Response(body, init);
}

function createFetch(response: Response): {
  fetchImpl: typeof fetch;
  requests: string[];
} {
  const requests: string[] = [];
  const fetchImpl: typeof fetch = async (input) => {
    requests.push(String(input));
    return response;
  };

  return { fetchImpl, requests };
}

describe("devicetree API client", () => {
  it("gets metadata from the metadata endpoint", async () => {
    const metadata: MetadataResponse = {
      filename: "board.dtb",
      file_size: 123,
      node_count: 3,
      property_count: 8,
      warnings: [],
      errors: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(metadata));

    await expect(getMetadata({ fetchImpl })).resolves.toEqual(metadata);
    expect(requests).toEqual(["/api/v1/metadata"]);
  });

  it("gets the Device Tree from the devicetree endpoint", async () => {
    const tree: DeviceTreeResponse = {
      node_count: 1,
      root: {
        id: "/",
        name: "/",
        full_name: "/",
        path: "/",
        unit_address: null,
        parent_path: null,
        properties: [],
        children: [],
      },
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(tree));

    await expect(getDeviceTree({ fetchImpl })).resolves.toEqual(tree);
    expect(requests).toEqual(["/api/v1/devicetree"]);
  });

  it("prefixes requests with baseUrl when provided", async () => {
    const { fetchImpl, requests } = createFetch(jsonResponse({}));

    await getMetadata({
      baseUrl: "http://localhost:8000/",
      fetchImpl,
    });

    expect(requests).toEqual(["http://localhost:8000/api/v1/metadata"]);
  });

  it("throws ApiError with structured detail for FastAPI error responses", async () => {
    const error: ErrorResponse = {
      detail: {
        source: "bad.dtb",
        warnings: [],
        errors: ["Failed to parse DTB"],
      },
    };
    const { fetchImpl } = createFetch(jsonResponse(error, { status: 422 }));

    await expect(getDeviceTree({ fetchImpl })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: error.detail,
      message: "Failed to parse DTB",
    } satisfies Partial<ApiError>);
  });

  it("throws ApiError for non-JSON HTTP errors", async () => {
    const { fetchImpl } = createFetch(
      textResponse("<html>bad gateway</html>", {
        status: 502,
        statusText: "Bad Gateway",
      }),
    );

    await expect(getDeviceTree({ fetchImpl })).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
      detail: null,
      message: "Bad Gateway",
    } satisfies Partial<ApiError>);
  });

  it("throws ApiError for successful non-JSON responses", async () => {
    const { fetchImpl } = createFetch(textResponse("<html>not json</html>"));

    await expect(getMetadata({ fetchImpl })).rejects.toMatchObject({
      name: "ApiError",
      status: 200,
      detail: null,
      message: "Invalid JSON response",
    } satisfies Partial<ApiError>);
  });

  it("throws ApiError for successful empty responses", async () => {
    const { fetchImpl } = createFetch(textResponse(""));

    await expect(getMetadata({ fetchImpl })).rejects.toMatchObject({
      name: "ApiError",
      status: 200,
      detail: null,
      message: "Invalid JSON response",
    } satisfies Partial<ApiError>);
  });
});
