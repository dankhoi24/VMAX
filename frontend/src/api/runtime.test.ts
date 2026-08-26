import { describe, expect, it } from "vitest";

import {
  ApiError,
  getRuntimeDevices,
  getRuntimeDrivers,
  getRuntimeIomem,
  getRuntimeInterrupts,
  getRuntimeMetadata,
} from "./runtime";
import type {
  RuntimeDevicesResponse,
  RuntimeDriversResponse,
  RuntimeIomemResponse,
  RuntimeInterruptsResponse,
  RuntimeMetadataResponse,
} from "../models/runtime";
import { formatHex } from "../models/runtime";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
    ...init,
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

describe("runtime API client", () => {
  it("gets runtime metadata from the metadata endpoint", async () => {
    const metadata: RuntimeMetadataResponse = {
      data: {
        hostname: "pi5",
        kernel_name: "Linux",
        kernel_release: "6.12.80-v8",
        kernel_version: "#1 SMP PREEMPT",
        machine: "aarch64",
        architecture: "arm64",
        cmdline: "console=ttyAMA10",
      },
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(metadata));

    await expect(getRuntimeMetadata({ fetchImpl })).resolves.toEqual(metadata);
    expect(requests).toEqual(["/api/v1/runtime/metadata"]);
  });

  it("gets runtime devices from the devices endpoint", async () => {
    const devices: RuntimeDevicesResponse = {
      data: [
        {
          name: "107d001000.serial",
          sysfs_path: "/sys/bus/platform/devices/107d001000.serial",
          bus: "platform",
          driver_name: "serial8250",
          driver_path: "/sys/bus/platform/drivers/serial8250",
          of_node_sysfs_path: null,
          subsystem_path: null,
          modalias: null,
          resources: [
            {
              index: 0,
              start: 0x107d001000,
              end: 0x107d0011ff,
              flags: 0x200,
              flag_names: ["MEM"],
              name: null,
              size: 0x200,
            },
          ],
          metadata: [],
        },
        {
          name: "fixedregulator_3v3",
          sysfs_path: "/sys/bus/platform/devices/fixedregulator_3v3",
          bus: "platform",
          driver_name: null,
          driver_path: null,
          of_node_sysfs_path: null,
          subsystem_path: null,
          modalias: null,
          resources: [],
          metadata: [["enabled", true]],
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(devices));

    await expect(getRuntimeDevices({ fetchImpl })).resolves.toEqual(devices);
    expect(requests).toEqual(["/api/v1/runtime/devices"]);
  });

  it("gets runtime drivers from the drivers endpoint", async () => {
    const drivers: RuntimeDriversResponse = {
      data: [
        {
          name: "serial8250",
          sysfs_path: "/sys/bus/platform/drivers/serial8250",
          bus: "platform",
          module_name: null,
          bound_device_paths: [
            "/sys/bus/platform/devices/107d001000.serial",
          ],
          metadata: [],
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(drivers));

    await expect(getRuntimeDrivers({ fetchImpl })).resolves.toEqual(drivers);
    expect(requests).toEqual(["/api/v1/runtime/drivers"]);
  });

  it("gets runtime iomem from the iomem endpoint", async () => {
    const iomem: RuntimeIomemResponse = {
      data: [
        {
          start: 0,
          end: 0x3fffffff,
          name: "System RAM",
          size: 0x40000000,
          children: [
            {
              start: 0x80000,
              end: 0x1fffff,
              name: "Kernel code",
              size: 0x180000,
              children: [],
            },
          ],
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(iomem));

    await expect(getRuntimeIomem({ fetchImpl })).resolves.toEqual(iomem);
    expect(requests).toEqual(["/api/v1/runtime/iomem"]);
  });

  it("gets runtime interrupts from the interrupts endpoint", async () => {
    const interrupts: RuntimeInterruptsResponse = {
      data: [
        {
          irq: 214,
          counts: [0, 4291, 0, 0],
          controller: "GICv3",
          hardware_irq: 182,
          trigger: "Level",
          actions: ["imr"],
          raw_line: "214: 0 4291 0 0 GICv3 182 Level imr",
          source_path: "/proc/interrupts",
          metadata: [["affinity", "0-3"]],
          total_count: 4291,
        },
      ],
      warnings: [],
    };
    const { fetchImpl, requests } = createFetch(jsonResponse(interrupts));

    await expect(getRuntimeInterrupts({ fetchImpl })).resolves.toEqual(
      interrupts,
    );
    expect(requests).toEqual(["/api/v1/runtime/interrupts"]);
  });

  it("preserves runtime warnings", async () => {
    const devices: RuntimeDevicesResponse = {
      data: [],
      warnings: [
        {
          code: "SYSFS_PLATFORM_DEVICES_READ_FAILED",
          message: "Unable to read /sys/bus/platform/devices",
          source_path: "/sys/bus/platform/devices",
        },
      ],
    };
    const { fetchImpl } = createFetch(jsonResponse(devices));

    const result = await getRuntimeDevices({ fetchImpl });

    expect(result.warnings).toEqual(devices.warnings);
  });

  it("keeps redacted iomem as data empty plus warning", async () => {
    const iomem: RuntimeIomemResponse = {
      data: [],
      warnings: [
        {
          code: "PROC_IOMEM_ADDRESSES_REDACTED",
          message: "/proc/iomem addresses are hidden",
          source_path: "/proc/iomem",
        },
      ],
    };
    const { fetchImpl } = createFetch(jsonResponse(iomem));

    const result = await getRuntimeIomem({ fetchImpl });

    expect(result.data).toEqual([]);
    expect(result.warnings[0].code).toBe("PROC_IOMEM_ADDRESSES_REDACTED");
  });

  it("prefixes runtime requests with baseUrl when provided", async () => {
    const { fetchImpl, requests } = createFetch(
      jsonResponse({ data: [], warnings: [] }),
    );

    await getRuntimeDrivers({
      baseUrl: "http://localhost:8000/",
      fetchImpl,
    });

    expect(requests).toEqual([
      "http://localhost:8000/api/v1/runtime/drivers",
    ]);
  });

  it("throws ApiError for HTTP failures", async () => {
    const { fetchImpl } = createFetch(
      jsonResponse(
        {
          detail: {
            source: null,
            warnings: [],
            errors: ["runtime failed"],
          },
        },
        { status: 500 },
      ),
    );

    await expect(getRuntimeMetadata({ fetchImpl })).rejects.toMatchObject({
      name: "ApiError",
      status: 500,
      message: "runtime failed",
    } satisfies Partial<ApiError>);
  });

  it("formats above-32-bit addresses without truncating upper bits", () => {
    expect(formatHex(0x107d001000)).toBe("0x107D001000");
  });
});
