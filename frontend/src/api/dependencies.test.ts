import { describe, expect, it } from "vitest";

import { getDependencyDevices } from "./dependencies";
import type { DependencyDevicesResponse } from "../models/dependency";

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

describe("dependency API client", () => {
  it("gets device dependency views from the dependencies endpoint", async () => {
    const response: DependencyDevicesResponse = {
      data: [
        {
          dt_node_path: "/soc/imr@e6260000",
          dependencies: [
            {
              kind: "interrupt",
              consumer_dt_path: "/soc/imr@e6260000",
              provider_dt_path: "/soc/interrupt-controller@f1000000",
              provider_phandle: 1,
              entry_index: 0,
              name: null,
              specifier_cells: [0, 150, 4],
              source_property: "interrupts",
              static_resolution: "resolved",
              evidence: [
                {
                  kind: "declared",
                  source: "devicetree",
                  source_path: "/soc/imr@e6260000/interrupts",
                  message: null,
                },
              ],
              interrupt_resolution: "resolved",
              interrupt_match_method: "controller_hardware_irq",
              runtime_interrupt: {
                irq: 214,
                counts: [0, 4291, 0, 0],
                controller: "GICv3",
                hardware_irq: 182,
                trigger: "Level",
                actions: ["imr"],
                total_count: 4291,
                source_path: "/proc/interrupts",
                metadata: [],
              },
              runtime_candidates: [
                {
                  irq: 214,
                  counts: [0, 4291, 0, 0],
                  controller: "GICv3",
                  hardware_irq: 182,
                  trigger: "Level",
                  actions: ["imr"],
                  total_count: 4291,
                  source_path: "/proc/interrupts",
                  metadata: [],
                },
              ],
              interrupt_warnings: [],
            },
          ],
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(response));

    await expect(getDependencyDevices({ fetchImpl })).resolves.toEqual(response);
    expect(requests).toEqual(["/api/v1/dependencies/devices"]);
  });

  it("preserves warnings and baseUrl", async () => {
    const response: DependencyDevicesResponse = {
      data: [],
      warnings: [
        {
          code: "PROC_INTERRUPTS_READ_FAILED",
          message: "Unable to read /proc/interrupts",
          consumer_dt_path: null,
          provider_dt_path: null,
          runtime_irq: null,
          source_path: "/proc/interrupts",
        },
      ],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(response));

    const result = await getDependencyDevices({
      baseUrl: "http://localhost:8000/",
      fetchImpl,
    });

    expect(result.warnings[0].code).toBe("PROC_INTERRUPTS_READ_FAILED");
    expect(requests).toEqual([
      "http://localhost:8000/api/v1/dependencies/devices",
    ]);
  });
});
