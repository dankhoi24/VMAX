import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getRuntimeDevices } from "../api/runtime";
import type {
  RuntimeDevice,
  RuntimeDevicesResponse,
} from "../models/runtime";
import { RuntimeDeviceBrowser } from "./RuntimeDeviceBrowser";

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
  };
});

const getRuntimeDevicesMock = vi.mocked(getRuntimeDevices);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const serialDevice: RuntimeDevice = {
  name: "107d001000.serial",
  sysfs_path: "/sys/bus/platform/devices/107d001000.serial",
  bus: "platform",
  driver_name: "serial8250",
  driver_path: "/sys/bus/platform/drivers/serial8250",
  of_node_sysfs_path: "/sys/firmware/devicetree/base/soc/serial@1000",
  subsystem_path: "/sys/bus/platform",
  modalias: "of:NserialT(null)Carm,pl011",
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
};

const regulatorDevice: RuntimeDevice = {
  name: "fixedregulator_3v3",
  sysfs_path: "/sys/bus/platform/devices/fixedregulator_3v3",
  bus: "platform",
  driver_name: null,
  driver_path: null,
  of_node_sysfs_path: null,
  subsystem_path: "/sys/bus/platform",
  modalias: null,
  resources: [],
  metadata: [],
};

const uncertainDevice: RuntimeDevice = {
  ...regulatorDevice,
  name: "device-a",
  sysfs_path: "/sys/bus/platform/devices/device-a",
};

function response(
  devices: RuntimeDevice[],
  warnings: RuntimeDevicesResponse["warnings"] = [],
): RuntimeDevicesResponse {
  return {
    data: devices,
    warnings,
  };
}

describe("RuntimeDeviceBrowser", () => {
  it("loads runtime devices on mount and selects the first device", async () => {
    getRuntimeDevicesMock.mockResolvedValue(
      response([serialDevice, regulatorDevice]),
    );

    render(<RuntimeDeviceBrowser />);

    expect(screen.getByText("Loading runtime devices...")).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: /107d001000\.serial/ }),
    ).toBeTruthy();
    expect(getRuntimeDevicesMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("2 devices")).toBeTruthy();
    expect(screen.getAllByText("bound").length).toBeGreaterThan(0);
    expect(screen.getByText("unbound")).toBeTruthy();

    const detail = screen.getByLabelText("Runtime device detail");
    expect(detail.textContent).toContain(
      "/sys/bus/platform/devices/107d001000.serial",
    );
    expect(detail.textContent).toContain("serial8250");
  });

  it("filters devices by driver, name, or bus", async () => {
    getRuntimeDevicesMock.mockResolvedValue(
      response([serialDevice, regulatorDevice]),
    );

    render(<RuntimeDeviceBrowser />);

    expect(
      await screen.findByRole("button", { name: /107d001000\.serial/ }),
    ).toBeTruthy();

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search runtime devices" }),
      { target: { value: "serial8250" } },
    );

    let list = screen.getByLabelText("Runtime device list");
    expect(within(list).getByText("107d001000.serial")).toBeTruthy();
    expect(within(list).queryByText("fixedregulator_3v3")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "Clear runtime device search" }),
    );
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search runtime devices" }),
      { target: { value: "fixedregulator" } },
    );

    list = screen.getByLabelText("Runtime device list");
    expect(within(list).getByText("fixedregulator_3v3")).toBeTruthy();
    expect(within(list).queryByText("107d001000.serial")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "Clear runtime device search" }),
    );
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search runtime devices" }),
      { target: { value: "platform" } },
    );

    list = screen.getByLabelText("Runtime device list");
    expect(within(list).getByText("107d001000.serial")).toBeTruthy();
    expect(within(list).getByText("fixedregulator_3v3")).toBeTruthy();
  });

  it("shows selected device details with runtime resource fields", async () => {
    getRuntimeDevicesMock.mockResolvedValue(
      response([serialDevice, regulatorDevice]),
    );

    render(<RuntimeDeviceBrowser />);

    expect(
      await screen.findByRole("button", { name: /107d001000\.serial/ }),
    ).toBeTruthy();

    const detail = screen.getByLabelText("Runtime device detail");
    expect(detail.textContent).toContain("1 resource");
    expect(detail.textContent).toContain("0x107D001000");
    expect(detail.textContent).toContain("0x107D0011FF");
    expect(detail.textContent).toContain("0x200");
    expect(detail.textContent).toContain("MEM");

    fireEvent.click(screen.getByRole("button", { name: /fixedregulator_3v3/ }));

    expect(detail.textContent).toContain("fixedregulator_3v3");
    expect(detail.textContent).toContain("0 resources");
    expect(detail.textContent).toContain(
      "No runtime resources exposed for this device.",
    );
  });

  it("marks binding as unknown when driver binding could not be inspected", async () => {
    getRuntimeDevicesMock.mockResolvedValue(
      response([uncertainDevice], [
        {
          code: "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
          message: "Unable to inspect driver binding",
          source_path: "/sys/bus/platform/devices/device-a/driver",
        },
      ]),
    );

    render(<RuntimeDeviceBrowser />);

    expect(
      await screen.findByRole("button", { name: /device-a/ }),
    ).toBeTruthy();
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.queryByText("unbound")).toBeNull();
    expect(screen.getByText("SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED")).toBeTruthy();
  });

  it("shows warnings without hiding successful device data", async () => {
    getRuntimeDevicesMock.mockResolvedValue(
      response([serialDevice], [
        {
          code: "SYSFS_PLATFORM_DEVICE_READ_FAILED",
          message: "Unable to inspect one platform device",
          source_path: "/sys/bus/platform/devices/bad-device",
        },
      ]),
    );

    render(<RuntimeDeviceBrowser />);

    expect(
      await screen.findByRole("button", { name: /107d001000\.serial/ }),
    ).toBeTruthy();
    expect(screen.getByText("SYSFS_PLATFORM_DEVICE_READ_FAILED")).toBeTruthy();
    expect(screen.getByText("Unable to inspect one platform device")).toBeTruthy();
    expect(screen.getByText("/sys/bus/platform/devices/bad-device")).toBeTruthy();
  });

  it("shows a fatal error when loading devices fails", async () => {
    getRuntimeDevicesMock.mockRejectedValue(new Error("runtime unavailable"));

    render(<RuntimeDeviceBrowser />);

    expect(await screen.findByText("Unable to load runtime devices")).toBeTruthy();
    expect(screen.getByText("runtime unavailable")).toBeTruthy();
    expect(screen.queryByText("107d001000.serial")).toBeNull();
  });

  it("shows an empty state for zero runtime devices", async () => {
    getRuntimeDevicesMock.mockResolvedValue(response([]));

    render(<RuntimeDeviceBrowser />);

    expect(await screen.findByText("No runtime devices found.")).toBeTruthy();
    expect(screen.getByLabelText("Runtime device detail").textContent).toContain(
      "Select a runtime device.",
    );
  });
});
