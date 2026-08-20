import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { RuntimeResource } from "../models/runtime";
import { RuntimeResourcePanel } from "./RuntimeResourcePanel";

afterEach(() => {
  cleanup();
});

const mmioResource: RuntimeResource = {
  index: 0,
  start: 0x107d001000,
  end: 0x107d0011ff,
  flags: 0x200,
  flag_names: ["MEM"],
  name: null,
  size: 0x200,
};

const namedIoResource: RuntimeResource = {
  index: 1,
  start: 0x3f8,
  end: 0x3ff,
  flags: 0x100,
  flag_names: ["IO", "IRQ"],
  name: "console-port",
  size: 0x8,
};

describe("RuntimeResourcePanel", () => {
  it("renders one runtime resource with exact hex fields", () => {
    render(<RuntimeResourcePanel resources={[mmioResource]} />);

    expect(screen.getByText("Runtime Resources")).toBeTruthy();
    expect(screen.getByText("Resource #0")).toBeTruthy();
    expect(screen.getAllByText("MEM").length).toBeGreaterThan(0);
    expect(screen.getByText("0x107D001000")).toBeTruthy();
    expect(screen.getByText("0x107D0011FF")).toBeTruthy();
    expect(screen.getAllByText("0x200").length).toBe(2);
  });

  it("renders multiple resources and decoded flag names", () => {
    render(<RuntimeResourcePanel resources={[mmioResource, namedIoResource]} />);

    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("Resource #0")).toBeTruthy();
    expect(screen.getByText("Resource #1")).toBeTruthy();
    expect(screen.getByText("IO | IRQ")).toBeTruthy();
    expect(screen.getByText("console-port")).toBeTruthy();
  });

  it("keeps raw flags visible even when decoded names exist", () => {
    render(<RuntimeResourcePanel resources={[namedIoResource]} />);

    const resource = screen.getByText("Resource #1").closest("li");
    expect(resource).not.toBeNull();
    expect(within(resource!).getByText("IO")).toBeTruthy();
    expect(within(resource!).getByText("IRQ")).toBeTruthy();
    expect(within(resource!).getByText("0x100")).toBeTruthy();
  });

  it("renders null names as unavailable without writing null", () => {
    render(<RuntimeResourcePanel resources={[mmioResource]} />);

    const resource = screen.getByText("Resource #0").closest("li");
    expect(resource).not.toBeNull();
    expect(within(resource!).getByText("-")).toBeTruthy();
    expect(resource!.textContent).not.toContain("null");
  });

  it("renders an unavailable empty state for devices without exposed resources", () => {
    render(<RuntimeResourcePanel resources={[]} />);

    expect(
      screen.getByText("No runtime resources exposed for this device."),
    ).toBeTruthy();
    expect(screen.queryByText("No resources")).toBeNull();
  });
});
