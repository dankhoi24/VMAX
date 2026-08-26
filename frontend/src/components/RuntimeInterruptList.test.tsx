import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getRuntimeInterrupts } from "../api/runtime";
import type {
  RuntimeInterrupt,
  RuntimeInterruptsResponse,
} from "../models/runtime";
import { RuntimeInterruptList } from "./RuntimeInterruptList";

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
    getRuntimeInterrupts: vi.fn(),
  };
});

const getRuntimeInterruptsMock = vi.mocked(getRuntimeInterrupts);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const imrInterrupt: RuntimeInterrupt = {
  irq: 214,
  counts: [0, 4291, 0, 0],
  controller: "GICv3",
  hardware_irq: 182,
  trigger: "Level",
  actions: ["imr"],
  raw_line: "214: 0 4291 0 0 GICv3 182 Level imr",
  source_path: "/proc/interrupts",
  metadata: [],
  total_count: 4291,
};

const ispInterrupt: RuntimeInterrupt = {
  ...imrInterrupt,
  irq: 215,
  hardware_irq: 183,
  actions: ["isp"],
  total_count: 105,
};

function response(
  data: RuntimeInterrupt[],
  warnings: RuntimeInterruptsResponse["warnings"] = [],
): RuntimeInterruptsResponse {
  return {
    data,
    warnings,
  };
}

describe("RuntimeInterruptList", () => {
  it("loads runtime interrupts and shows IRQ inventory fields", async () => {
    getRuntimeInterruptsMock.mockResolvedValue(response([imrInterrupt]));

    render(<RuntimeInterruptList />);

    expect(screen.getByText("Loading runtime interrupts...")).toBeTruthy();
    expect(await screen.findByText("IRQ 214")).toBeTruthy();
    expect(getRuntimeInterruptsMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("1 IRQs")).toBeTruthy();
    expect(screen.getByText("GICv3")).toBeTruthy();
    expect(screen.getByText("182 (0xB6)")).toBeTruthy();
    expect(screen.getByText("imr")).toBeTruthy();
    expect(screen.getByText("4,291 total")).toBeTruthy();
  });

  it("filters interrupts by action and controller", async () => {
    getRuntimeInterruptsMock.mockResolvedValue(
      response([imrInterrupt, ispInterrupt]),
    );

    render(<RuntimeInterruptList />);

    expect(await screen.findByText("IRQ 214")).toBeTruthy();

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search runtime interrupts" }),
      { target: { value: "isp" } },
    );

    const list = screen.getByLabelText("Runtime interrupt list");
    expect(within(list).getByText("IRQ 215")).toBeTruthy();
    expect(within(list).queryByText("IRQ 214")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "Clear runtime interrupt search" }),
    );
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search runtime interrupts" }),
      { target: { value: "gicv3" } },
    );

    expect(within(list).getByText("IRQ 214")).toBeTruthy();
    expect(within(list).getByText("IRQ 215")).toBeTruthy();
  });

  it("shows warnings without hiding valid interrupts", async () => {
    getRuntimeInterruptsMock.mockResolvedValue(
      response([imrInterrupt], [
        {
          code: "PROC_INTERRUPTS_PARSE_FAILED",
          message: "Unable to parse one /proc/interrupts line",
          source_path: "/proc/interrupts",
        },
      ]),
    );

    render(<RuntimeInterruptList />);

    expect(await screen.findByText("IRQ 214")).toBeTruthy();
    expect(screen.getByText("PROC_INTERRUPTS_PARSE_FAILED")).toBeTruthy();
    expect(screen.getByText("Unable to parse one /proc/interrupts line")).toBeTruthy();
  });

  it("shows empty and fatal error states", async () => {
    getRuntimeInterruptsMock.mockResolvedValueOnce(response([]));

    const { unmount } = render(<RuntimeInterruptList />);

    expect(
      await screen.findByText("No runtime interrupts reported by the current source."),
    ).toBeTruthy();

    unmount();
    getRuntimeInterruptsMock.mockRejectedValueOnce(new Error("interrupts failed"));

    render(<RuntimeInterruptList />);

    expect(await screen.findByText("Unable to load runtime interrupts")).toBeTruthy();
    expect(screen.getByText("interrupts failed")).toBeTruthy();
  });
});
