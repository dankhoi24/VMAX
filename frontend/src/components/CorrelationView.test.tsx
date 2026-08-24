import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getCorrelationDevices } from "../api/correlation";
import type {
  CorrelatedDevice,
  CorrelationDevicesResponse,
} from "../models/correlation";
import { CorrelationView } from "./CorrelationView";

vi.mock("../api/correlation", () => {
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
    getCorrelationDevices: vi.fn(),
  };
});

const getCorrelationDevicesMock = vi.mocked(getCorrelationDevices);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const exactSerial: CorrelatedDevice = {
  dt_node_path: "/soc/serial@e6e60000",
  runtime_device: {
    name: "e6e60000.serial",
    sysfs_path: "/sys/bus/platform/devices/e6e60000.serial",
    bus: "platform",
    driver_name: "sh-sci",
    driver_path: "/sys/bus/platform/drivers/sh-sci",
    of_node_sysfs_path: "/sys/firmware/devicetree/base/soc/serial@e6e60000",
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
};

const unmatchedGpio: CorrelatedDevice = {
  dt_node_path: "/soc/gpio@e6050000",
  runtime_device: null,
  runtime_driver: null,
  static_regions: [
    {
      node_path: "/soc/gpio@e6050000",
      bus_address: "0xe6050000",
      cpu_start: "0xe6050000",
      size: "0x100",
      cpu_end: "0xe60500ff",
    },
  ],
  address_matches: [
    {
      dt_start: "0xe6050000",
      dt_end: "0xe60500ff",
      iomem_start: null,
      iomem_end: null,
      iomem_name: null,
      match_type: "none",
      candidates: [],
    },
  ],
  match_method: "unmatched",
  warnings: [],
};

const unavailableI2c: CorrelatedDevice = {
  dt_node_path: "/soc/i2c@e6500000",
  runtime_device: null,
  runtime_driver: null,
  static_regions: [
    {
      node_path: "/soc/i2c@e6500000",
      bus_address: "0xe6500000",
      cpu_start: "0xe6500000",
      size: "0x100",
      cpu_end: "0xe65000ff",
    },
  ],
  address_matches: [
    {
      dt_start: "0xe6500000",
      dt_end: "0xe65000ff",
      iomem_start: null,
      iomem_end: null,
      iomem_name: null,
      match_type: "unavailable",
      candidates: [],
    },
  ],
  match_method: "unavailable",
  warnings: [],
};

const partialDriverSerial: CorrelatedDevice = {
  ...exactSerial,
  runtime_driver: null,
};

const unknownBindingSerial: CorrelatedDevice = {
  ...exactSerial,
  runtime_device: {
    ...exactSerial.runtime_device!,
    driver_name: null,
    driver_path: null,
  },
  runtime_driver: null,
};

function response(
  data: CorrelatedDevice[],
  warnings: CorrelationDevicesResponse["warnings"] = [],
): CorrelationDevicesResponse {
  return {
    data,
    warnings,
  };
}

describe("CorrelationView", () => {
  it("loads correlation data and shows DT, runtime, driver, and address relation", async () => {
    getCorrelationDevicesMock.mockResolvedValue(response([exactSerial]));

    render(<CorrelationView />);

    expect(screen.getByText("Loading correlation data...")).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: /\/soc\/serial@e6e60000/ }),
    ).toBeTruthy();
    expect(getCorrelationDevicesMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("1 relations")).toBeTruthy();

    const detail = screen.getByLabelText("Correlation detail");
    expect(detail.textContent).toContain("/soc/serial@e6e60000");
    expect(detail.textContent).toContain("e6e60000.serial");
    expect(detail.textContent).toContain("sh-sci");
    expect(detail.textContent).toContain("0xe6e60000 - 0xe6e600ff");
    expect(detail.textContent).toContain("DT physical range equals");
  });

  it("filters by status without rendering unavailable as unmatched", async () => {
    getCorrelationDevicesMock.mockResolvedValue(
      response([exactSerial, unmatchedGpio, unavailableI2c]),
    );

    render(<CorrelationView />);

    expect(
      await screen.findByRole("button", { name: /\/soc\/serial@e6e60000/ }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /unavailable 1/i }));

    const list = screen.getByLabelText("Correlation device list");
    expect(within(list).getByText("/soc/i2c@e6500000")).toBeTruthy();
    expect(within(list).queryByText("/soc/gpio@e6050000")).toBeNull();

    const detail = screen.getByLabelText("Correlation detail");
    expect(detail.textContent).toContain("UNAVAILABLE");
    expect(detail.textContent).toContain("runtime device unknown");
    expect(detail.textContent).toContain("driver unknown");
    expect(detail.textContent).toContain("Source data is incomplete");
    expect(detail.textContent).not.toContain("Source scan completed");

    const row = within(list).getByRole("button", {
      name: /runtime device unknown \/ driver unknown/,
    });
    expect(row).toBeTruthy();
    expect(detail.textContent).not.toContain("no runtime device");
  });

  it("preserves driver binding evidence when driver inventory is incomplete", async () => {
    getCorrelationDevicesMock.mockResolvedValue(response([partialDriverSerial]));

    render(<CorrelationView />);

    const row = await screen.findByRole("button", {
      name: /e6e60000\.serial \/ sh-sci/,
    });
    expect(row).toBeTruthy();

    const detail = screen.getByLabelText("Correlation detail");
    expect(detail.textContent).toContain("driver binding");
    expect(detail.textContent).toContain("sh-sci");
    expect(detail.textContent).toContain("/sys/bus/platform/drivers/sh-sci");
    expect(detail.textContent).toContain("driver details unavailable");
    expect(detail.textContent).not.toContain("no driver");
  });

  it("shows unknown instead of unbound when driver binding read failed", async () => {
    getCorrelationDevicesMock.mockResolvedValue(
      response([unknownBindingSerial], [
        {
          code: "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
          message: "Unable to read driver binding",
          dt_node_path: "/soc/serial@e6e60000",
          runtime_device_path: "/sys/bus/platform/devices/e6e60000.serial",
          source_path: "/sys/bus/platform/devices/e6e60000.serial/driver",
        },
      ]),
    );

    render(<CorrelationView />);

    const row = await screen.findByRole("button", {
      name: /e6e60000\.serial \/ unknown/,
    });
    expect(row).toBeTruthy();

    const detail = screen.getByLabelText("Correlation detail");
    expect(detail.textContent).toContain("driver binding");
    expect(detail.textContent).toContain("unknown");
    expect(detail.textContent).toContain("driver binding unknown");
    expect(detail.textContent).not.toContain("unbound");
  });

  it("searches by runtime driver and device name", async () => {
    getCorrelationDevicesMock.mockResolvedValue(
      response([exactSerial, unmatchedGpio]),
    );

    render(<CorrelationView />);

    expect(
      await screen.findByRole("button", { name: /\/soc\/serial@e6e60000/ }),
    ).toBeTruthy();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search correlations" }), {
      target: { value: "sh-sci" },
    });

    const list = screen.getByLabelText("Correlation device list");
    expect(within(list).getByText("/soc/serial@e6e60000")).toBeTruthy();
    expect(within(list).queryByText("/soc/gpio@e6050000")).toBeNull();
  });

  it("shows ambiguous candidates explicitly", async () => {
    const ambiguous: CorrelatedDevice = {
      ...exactSerial,
      address_matches: [
        {
          dt_start: "0xe6e60000",
          dt_end: "0xe6e600ff",
          iomem_start: null,
          iomem_end: null,
          iomem_name: null,
          match_type: "ambiguous",
          candidates: [
            {
              start: "0xe6e60000",
              end: "0xe6e600ff",
              name: "serial-a",
            },
            {
              start: "0xe6e60000",
              end: "0xe6e600ff",
              name: "serial-b",
            },
          ],
        },
      ],
    };
    getCorrelationDevicesMock.mockResolvedValue(response([ambiguous]));

    render(<CorrelationView />);

    expect(await screen.findByText("Candidates")).toBeTruthy();
    expect(screen.getByText("serial-a")).toBeTruthy();
    expect(screen.getByText("serial-b")).toBeTruthy();
    expect(screen.getByText("Multiple /proc/iomem candidates match this DT range."))
      .toBeTruthy();
  });

  it("renders warnings while preserving successful data", async () => {
    getCorrelationDevicesMock.mockResolvedValue(
      response([exactSerial], [
        {
          code: "SYSFS_PLATFORM_DEVICE_READ_FAILED",
          message: "Unable to inspect one platform device",
          dt_node_path: null,
          runtime_device_path: null,
          source_path: "/sys/bus/platform/devices/bad-device",
        },
      ]),
    );

    render(<CorrelationView />);

    expect(
      await screen.findByRole("button", { name: /\/soc\/serial@e6e60000/ }),
    ).toBeTruthy();
    expect(screen.getByText("SYSFS_PLATFORM_DEVICE_READ_FAILED")).toBeTruthy();
    expect(screen.getByText("Unable to inspect one platform device")).toBeTruthy();
    expect(screen.getByText("/sys/bus/platform/devices/bad-device")).toBeTruthy();
  });

  it("shows empty and fatal error states", async () => {
    getCorrelationDevicesMock.mockResolvedValueOnce(response([]));

    const { unmount } = render(<CorrelationView />);

    expect(
      await screen.findByText("No correlation rows reported by the current source."),
    ).toBeTruthy();

    unmount();
    getCorrelationDevicesMock.mockRejectedValueOnce(new Error("correlation failed"));

    render(<CorrelationView />);

    expect(await screen.findByText("Unable to load correlation data")).toBeTruthy();
    expect(screen.getByText("correlation failed")).toBeTruthy();
  });
});
