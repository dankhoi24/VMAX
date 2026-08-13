import { describe, expect, it } from "vitest";

import { getAddressingReport } from "./addressing";
import type { AddressingReport } from "../models/addressing";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
  });
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

describe("addressing API client", () => {
  it("gets the addressing report from the addressing endpoint", async () => {
    const report: AddressingReport = {
      regions: [
        {
          node_path: "/soc/uart@1000",
          kind: "device",
          start: "0x107d001000",
          size: "0x100",
          end: "0x107d0010ff",
        },
      ],
      mappings: [],
      translations: [],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(report));

    await expect(getAddressingReport({ fetchImpl })).resolves.toEqual(report);
    expect(requests).toEqual(["/api/v1/addressing"]);
  });

  it("preserves exact hex strings without numeric conversion", async () => {
    const report: AddressingReport = {
      regions: [
        {
          node_path: "/soc/device@0",
          kind: "device",
          start: "0xfffffffffffff000",
          size: "0x1000",
          end: "0xffffffffffffffff",
        },
      ],
      mappings: [
        {
          node_path: "/soc",
          index: 0,
          child_address: "0x0",
          parent_address: "0xfffffffffffff000",
          size: "0x1000",
          source_property: "ranges",
        },
      ],
      translations: [],
      warnings: [],
    };
    const { fetchImpl } = createFetch(jsonResponse(report));

    const result = await getAddressingReport({ fetchImpl });

    expect(result.regions[0].start).toBe("0xfffffffffffff000");
    expect(result.regions[0].end).toBe("0xffffffffffffffff");
    expect(result.mappings[0].parent_address).toBe("0xfffffffffffff000");
  });
});
