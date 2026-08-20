import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getRuntimeDevices,
  getRuntimeDrivers,
  getRuntimeIomem,
  getRuntimeMetadata,
} from "../api/runtime";
import type { IomemRegion, RuntimeIomemResponse } from "../models/runtime";
import { RuntimeAddressMap } from "./RuntimeAddressMap";

vi.mock("../api/runtime", () => {
  class ApiError extends Error {
    readonly status: number;
    readonly detail: { errors: string[] } | null;

    constructor(
      message: string,
      status: number,
      detail: { errors: string[] } | null = null,
    ) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.detail = detail;
    }
  }

  return {
    ApiError,
    getRuntimeDevices: vi.fn(),
    getRuntimeDrivers: vi.fn(),
    getRuntimeIomem: vi.fn(),
    getRuntimeMetadata: vi.fn(),
  };
});

const getRuntimeDevicesMock = vi.mocked(getRuntimeDevices);
const getRuntimeDriversMock = vi.mocked(getRuntimeDrivers);
const getRuntimeIomemMock = vi.mocked(getRuntimeIomem);
const getRuntimeMetadataMock = vi.mocked(getRuntimeMetadata);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const systemRam: IomemRegion = {
  start: 0,
  end: 0x3fffffff,
  name: "System RAM",
  size: 0x40000000,
  children: [
    {
      start: 0x80000,
      end: 0xffffff,
      name: "Kernel code",
      size: 0xf80000,
      children: [],
    },
    {
      start: 0x1000000,
      end: 0x1ffffff,
      name: "Kernel data",
      size: 0x1000000,
      children: [],
    },
  ],
};

const serialRegion: IomemRegion = {
  start: 0x107d001000,
  end: 0x107d001fff,
  name: "serial@107d001000",
  size: 0x1000,
  children: [],
};

function response(
  data: IomemRegion[],
  warnings: RuntimeIomemResponse["warnings"] = [],
): RuntimeIomemResponse {
  return {
    data,
    warnings,
  };
}

describe("RuntimeAddressMap", () => {
  it("loads runtime iomem once without calling other runtime endpoints", async () => {
    getRuntimeIomemMock.mockResolvedValue(response([systemRam]));

    render(<RuntimeAddressMap />);

    expect(screen.getByText("Loading runtime address map...")).toBeTruthy();
    expect(await screen.findByText("System RAM")).toBeTruthy();
    expect(getRuntimeIomemMock).toHaveBeenCalledTimes(1);
    expect(getRuntimeDevicesMock).not.toHaveBeenCalled();
    expect(getRuntimeDriversMock).not.toHaveBeenCalled();
    expect(getRuntimeMetadataMock).not.toHaveBeenCalled();
  });

  it("renders nested /proc/iomem hierarchy without flattening children away", async () => {
    getRuntimeIomemMock.mockResolvedValue(response([systemRam]));

    render(<RuntimeAddressMap />);

    const rootRegion = await screen.findByRole("article", {
      name: "Runtime region System RAM",
    });
    expect(within(rootRegion).getByText("0x0")).toBeTruthy();
    expect(within(rootRegion).getByText("0x3FFFFFFF")).toBeTruthy();
    expect(within(rootRegion).getByText("0x40000000")).toBeTruthy();
    expect(within(rootRegion).getByText("2 children")).toBeTruthy();
    expect(screen.getByRole("article", { name: "Runtime region Kernel code" }))
      .toBeTruthy();
    expect(screen.getByRole("article", { name: "Runtime region Kernel data" }))
      .toBeTruthy();
  });

  it("renders multiple roots and preserves above-32-bit addresses", async () => {
    getRuntimeIomemMock.mockResolvedValue(response([systemRam, serialRegion]));

    render(<RuntimeAddressMap />);

    expect(await screen.findByText("2 root regions")).toBeTruthy();
    expect(screen.getByText("serial@107d001000")).toBeTruthy();
    expect(screen.getByText("0x107D001000")).toBeTruthy();
    expect(screen.getByText("0x107D001FFF")).toBeTruthy();
    expect(screen.getByText("0x1000")).toBeTruthy();
  });

  it("shows partial warnings while still rendering valid regions", async () => {
    getRuntimeIomemMock.mockResolvedValue(
      response([systemRam], [
        {
          code: "PROC_IOMEM_ROW_MALFORMED",
          message: "Unable to parse one /proc/iomem row",
          source_path: "/proc/iomem",
        },
      ]),
    );

    render(<RuntimeAddressMap />);

    expect(await screen.findByText("System RAM")).toBeTruthy();
    expect(screen.getByText("PROC_IOMEM_ROW_MALFORMED")).toBeTruthy();
    expect(screen.getByText("Unable to parse one /proc/iomem row")).toBeTruthy();
    expect(screen.getByText("/proc/iomem")).toBeTruthy();
  });

  it("shows a redacted state instead of rendering zero address ranges", async () => {
    getRuntimeIomemMock.mockResolvedValue(
      response([], [
        {
          code: "PROC_IOMEM_ADDRESSES_REDACTED",
          message: "/proc/iomem addresses are hidden",
          source_path: "/proc/iomem",
        },
      ]),
    );

    render(<RuntimeAddressMap />);

    expect(
      await screen.findByText("Runtime address information is unavailable."),
    ).toBeTruthy();
    expect(
      screen.getByText("The kernel is hiding /proc/iomem addresses."),
    ).toBeTruthy();
    expect(screen.queryByText("0x0 - 0x0")).toBeNull();
  });

  it("shows a neutral empty state for legitimate empty responses", async () => {
    getRuntimeIomemMock.mockResolvedValue(response([]));

    render(<RuntimeAddressMap />);

    expect(
      await screen.findByText(
        "No runtime address regions reported by the current source.",
      ),
    ).toBeTruthy();
  });

  it("shows a fatal error when loading runtime iomem fails", async () => {
    getRuntimeIomemMock.mockRejectedValue(new Error("iomem unavailable"));

    render(<RuntimeAddressMap />);

    expect(await screen.findByText("Unable to load runtime address map"))
      .toBeTruthy();
    expect(screen.getByText("iomem unavailable")).toBeTruthy();
  });

  it("does not infer Device Tree or runtime device ownership", async () => {
    getRuntimeIomemMock.mockResolvedValue(response([serialRegion]));

    render(<RuntimeAddressMap />);

    expect(await screen.findByText("serial@107d001000")).toBeTruthy();
    expect(screen.queryByText(/Device Tree/i)).toBeNull();
    expect(screen.queryByText(/owner/i)).toBeNull();
    expect(screen.queryByText(/driver/i)).toBeNull();
  });
});
