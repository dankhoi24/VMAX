import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getDependencyDevices } from "../api/dependencies";
import type {
  DependencyDevicesResponse,
  DependencyRuntimeInterrupt,
  DeviceDependency,
  DeviceDependencyView,
} from "../models/dependency";
import { DependencyPanel } from "./DependencyPanel";

vi.mock("../api/dependencies", () => {
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
    getDependencyDevices: vi.fn(),
  };
});

const getDependencyDevicesMock = vi.mocked(getDependencyDevices);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const clockDependency: DeviceDependency = {
  kind: "clock",
  consumer_dt_path: "/soc/imr@e6260000",
  provider_dt_path: "/soc/cpg@e6150000",
  provider_phandle: 12,
  entry_index: 0,
  name: "fck",
  specifier_cells: [12, 4],
  source_property: "clocks",
  static_resolution: "resolved",
  evidence: [
    {
      kind: "declared",
      source: "devicetree",
      source_path: "/soc/imr@e6260000/clocks",
      message: null,
    },
  ],
  interrupt_resolution: null,
  interrupt_match_method: null,
  runtime_interrupt: null,
  runtime_candidates: [],
  interrupt_warnings: [],
};

const imrRuntimeInterrupt: DependencyRuntimeInterrupt = {
  irq: 214,
  counts: [0, 4291, 0, 0],
  controller: "GICv3",
  hardware_irq: 182,
  trigger: "Level",
  actions: ["imr"],
  total_count: 4291,
  source_path: "/proc/interrupts",
  metadata: [],
};

const interruptDependency: DeviceDependency = {
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
  runtime_interrupt: imrRuntimeInterrupt,
  runtime_candidates: [imrRuntimeInterrupt],
  interrupt_warnings: [],
};

const imrView: DeviceDependencyView = {
  dt_node_path: "/soc/imr@e6260000",
  dependencies: [clockDependency, interruptDependency],
};

function response(
  data: DeviceDependencyView[],
  warnings: DependencyDevicesResponse["warnings"] = [],
): DependencyDevicesResponse {
  return {
    data,
    warnings,
  };
}

describe("DependencyPanel", () => {
  it("loads dependencies and separates static dependency from runtime IRQ state", async () => {
    getDependencyDevicesMock.mockResolvedValue(response([imrView]));

    render(<DependencyPanel />);

    expect(screen.getByText("Loading device dependencies...")).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: /\/soc\/imr@e6260000/ }),
    ).toBeTruthy();
    expect(getDependencyDevicesMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("2 dependencies")).toBeTruthy();

    const detail = screen.getByLabelText("Dependency detail");
    expect(detail.textContent).toContain("/soc/imr@e6260000");
    expect(detail.textContent).toContain("CLOCK");
    expect(detail.textContent).toContain("/soc/cpg@e6150000");
    expect(detail.textContent).toContain("INTERRUPT");
    expect(detail.textContent).toContain("Static");
    expect(detail.textContent).toContain("Runtime");
    expect(detail.textContent).toContain("Linux IRQ");
    expect(detail.textContent).toContain("214");
    expect(detail.textContent).toContain("GICv3");
    expect(detail.textContent).toContain("4,291");
    expect(detail.textContent).toContain("<0x0 0x96 0x4>");
    expect(detail.textContent).toContain("182 (0xB6)");
    expect(screen.queryByText("Candidates")).toBeNull();
  });

  it("filters dependencies by provider and runtime action", async () => {
    const i2cView: DeviceDependencyView = {
      dt_node_path: "/soc/i2c@e6500000",
      dependencies: [
        {
          ...clockDependency,
          consumer_dt_path: "/soc/i2c@e6500000",
          provider_dt_path: "/soc/cpg@e6150000",
        },
      ],
    };
    getDependencyDevicesMock.mockResolvedValue(response([imrView, i2cView]));

    render(<DependencyPanel />);

    expect(
      await screen.findByRole("button", { name: /\/soc\/imr@e6260000/ }),
    ).toBeTruthy();

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search dependencies" }),
      { target: { value: "imr" } },
    );

    const list = screen.getByLabelText("Dependency device list");
    expect(within(list).getByText("/soc/imr@e6260000")).toBeTruthy();
    expect(within(list).queryByText("/soc/i2c@e6500000")).toBeNull();
  });

  it("selects provider devices from the focus graph", async () => {
    getDependencyDevicesMock.mockResolvedValue(
      response([
        imrView,
        {
          dt_node_path: "/soc/cpg@e6150000",
          dependencies: [],
        },
      ]),
    );

    render(<DependencyPanel />);

    expect(await screen.findByText("Focus Graph")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Select dependency graph node cpg@e6150000",
      }),
    );

    const detail = screen.getByLabelText("Dependency detail");
    expect(detail.textContent).toContain("/soc/cpg@e6150000");
  });

  it("shows ambiguous runtime IRQ candidates explicitly", async () => {
    const ambiguousInterrupt: DeviceDependency = {
      ...interruptDependency,
      interrupt_resolution: "ambiguous",
      runtime_interrupt: null,
      runtime_candidates: [
        interruptDependency.runtime_interrupt!,
        {
          ...interruptDependency.runtime_interrupt!,
          irq: 215,
          actions: ["imr-alt"],
        },
      ],
    };
    getDependencyDevicesMock.mockResolvedValue(
      response([
        {
          dt_node_path: "/soc/imr@e6260000",
          dependencies: [ambiguousInterrupt],
        },
      ]),
    );

    render(<DependencyPanel />);

    expect(await screen.findByText("Candidates")).toBeTruthy();
    const detail = screen.getByLabelText("Dependency detail");
    expect(detail.textContent).toContain("RuntimeAMBIGUOUS");
    expect(detail.textContent).toContain("IRQ");
    expect(detail.textContent).toContain("214");
    expect(detail.textContent).toContain("215");
    expect(detail.textContent).toContain("imr-alt");
  });

  it("surfaces warnings without hiding static dependency data", async () => {
    const unavailableInterrupt: DeviceDependency = {
      ...interruptDependency,
      interrupt_resolution: "unavailable",
      runtime_interrupt: null,
      interrupt_warnings: [
        {
          code: "PROC_INTERRUPTS_READ_FAILED",
          message: "Unable to read /proc/interrupts",
          consumer_dt_path: "/soc/imr@e6260000",
          provider_dt_path: "/soc/interrupt-controller@f1000000",
          runtime_irq: null,
          source_path: "/proc/interrupts",
        },
      ],
    };
    getDependencyDevicesMock.mockResolvedValue(
      response(
        [
          {
            dt_node_path: "/soc/imr@e6260000",
            dependencies: [clockDependency, unavailableInterrupt],
          },
        ],
        [
          {
            code: "PROC_INTERRUPTS_READ_FAILED",
            message: "Unable to read /proc/interrupts",
            consumer_dt_path: null,
            provider_dt_path: null,
            runtime_irq: null,
            source_path: "/proc/interrupts",
          },
        ],
      ),
    );

    render(<DependencyPanel />);

    expect(
      (await screen.findAllByText("PROC_INTERRUPTS_READ_FAILED")).length,
    ).toBeGreaterThan(0);
    const detail = screen.getByLabelText("Dependency detail");
    expect(detail.textContent).toContain("/soc/cpg@e6150000");
    expect(detail.textContent).toContain("RuntimeUNAVAILABLE");
    expect(detail.textContent).toContain(
      "Runtime interrupt data is not resolved",
    );
  });

  it("shows empty and fatal error states", async () => {
    getDependencyDevicesMock.mockResolvedValueOnce(response([]));

    const { unmount } = render(<DependencyPanel />);

    expect(
      await screen.findByText("No dependency views reported by the current source."),
    ).toBeTruthy();

    unmount();
    getDependencyDevicesMock.mockRejectedValueOnce(new Error("dependency failed"));

    render(<DependencyPanel />);

    expect(await screen.findByText("Unable to load device dependencies")).toBeTruthy();
    expect(screen.getByText("dependency failed")).toBeTruthy();
  });
});
