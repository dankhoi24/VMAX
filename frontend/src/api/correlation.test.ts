import { describe, expect, it } from "vitest";

import { getCorrelationDevices } from "./correlation";
import type { CorrelationDevicesResponse } from "../models/correlation";

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

describe("correlation API client", () => {
  it("gets correlated devices from the correlation endpoint", async () => {
    const response: CorrelationDevicesResponse = {
      data: [
        {
          dt_node_path: "/soc/serial@e6e60000",
          runtime_device: {
            name: "e6e60000.serial",
            sysfs_path: "/sys/bus/platform/devices/e6e60000.serial",
            bus: "platform",
            driver_name: "sh-sci",
            driver_path: "/sys/bus/platform/drivers/sh-sci",
            of_node_sysfs_path:
              "/sys/firmware/devicetree/base/soc/serial@e6e60000",
          },
          runtime_driver: {
            name: "sh-sci",
            sysfs_path: "/sys/bus/platform/drivers/sh-sci",
            bus: "platform",
            module_name: null,
          },
          static_regions: [
            {
              node_path: "/soc/serial@e6e60000",
              bus_address: "0xe6e60000",
              cpu_start: "0xe6e60000",
              size: "0x100",
              cpu_end: "0xe6e600ff",
            },
          ],
          address_matches: [
            {
              dt_start: "0xe6e60000",
              dt_end: "0xe6e600ff",
              iomem_start: "0xe6e60000",
              iomem_end: "0xe6e600ff",
              iomem_name: "e6e60000.serial",
              match_type: "exact",
              candidates: [
                {
                  start: "0xe6e60000",
                  end: "0xe6e600ff",
                  name: "e6e60000.serial",
                },
              ],
            },
          ],
          match_method: "exact_of_node",
          warnings: [],
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(response));

    await expect(getCorrelationDevices({ fetchImpl })).resolves.toEqual(response);
    expect(requests).toEqual(["/api/v1/correlation/devices"]);
  });

  it("preserves exact hex strings and unavailable semantics", async () => {
    const response: CorrelationDevicesResponse = {
      data: [
        {
          dt_node_path: "/soc/device@0",
          runtime_device: null,
          runtime_driver: null,
          static_regions: [
            {
              node_path: "/soc/device@0",
              bus_address: "0xfffffffffffff000",
              cpu_start: "0xfffffffffffff000",
              size: "0x1000",
              cpu_end: "0xffffffffffffffff",
            },
          ],
          address_matches: [
            {
              dt_start: "0xfffffffffffff000",
              dt_end: "0xffffffffffffffff",
              iomem_start: null,
              iomem_end: null,
              iomem_name: null,
              match_type: "unavailable",
              candidates: [],
            },
          ],
          match_method: "unavailable",
          warnings: [],
        },
      ],
      warnings: [],
    };
    const { fetchImpl } = createFetch(jsonResponse(response));

    const result = await getCorrelationDevices({ fetchImpl });

    expect(result.data[0].match_method).toBe("unavailable");
    expect(result.data[0].static_regions[0].cpu_end).toBe(
      "0xffffffffffffffff",
    );
    expect(result.data[0].address_matches[0].match_type).toBe("unavailable");
  });

  it("prefixes correlation requests with baseUrl when provided", async () => {
    const { fetchImpl, requests } = createFetch(
      jsonResponse({ data: [], warnings: [] }),
    );

    await getCorrelationDevices({
      baseUrl: "http://localhost:8000/",
      fetchImpl,
    });

    expect(requests).toEqual([
      "http://localhost:8000/api/v1/correlation/devices",
    ]);
  });
});
