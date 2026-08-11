import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PropertyPanel } from "./PropertyPanel";
import type { DeviceTreeNode } from "../models/devicetree";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const node: DeviceTreeNode = {
  id: "/soc@107c000000",
  name: "soc",
  full_name: "soc@107c000000",
  path: "/soc@107c000000",
  unit_address: "107c000000",
  parent_path: "/",
  properties: [
    {
      name: "compatible",
      kind: "string_list",
      value: ["simple-bus"],
      raw_hex: "73696d706c652d62757300",
    },
    {
      name: "#address-cells",
      kind: "cells",
      value: [2],
      raw_hex: "00000002",
    },
    {
      name: "ranges",
      kind: "cells",
      value: [0, 0, 1, 0],
      raw_hex: "00000000000000000000000100000000",
    },
  ],
  children: [],
};

describe("PropertyPanel", () => {
  it("renders an empty state when no node is selected", () => {
    render(<PropertyPanel node={null} />);

    expect(screen.getByText("Select a node to inspect.")).toBeTruthy();
  });

  it("renders selected node metadata", () => {
    render(<PropertyPanel node={node} />);

    expect(screen.getByText("soc@107c000000")).toBeTruthy();
    expect(screen.getByText("/soc@107c000000")).toBeTruthy();
    expect(screen.getByText("107c000000")).toBeTruthy();
    expect(screen.getByText("/")).toBeTruthy();
  });

  it("renders property kind, value, and raw bytes without interpretation", () => {
    render(<PropertyPanel node={node} />);

    expect(screen.getByText("compatible")).toBeTruthy();
    expect(screen.getByText("string_list")).toBeTruthy();
    expect(
      screen.getByText("string_list").classList.contains("property-kind-string-list"),
    ).toBe(true);
    expect(screen.getByText("[\"simple-bus\"]")).toBeTruthy();
    expect(screen.getByText("73696d706c652d62757300")).toBeTruthy();

    expect(screen.getByText("#address-cells")).toBeTruthy();
    const cellBadges = screen.getAllByText("cells");
    expect(cellBadges).toHaveLength(2);
    expect(cellBadges[0].classList.contains("property-kind-cells")).toBe(true);
    expect(screen.getByText("[2]")).toBeTruthy();
    expect(screen.getByText("00000002")).toBeTruthy();

    expect(screen.getByText("ranges")).toBeTruthy();
    expect(screen.getByText("[0,0,1,0]")).toBeTruthy();
    expect(screen.getByText("00000000000000000000000100000000")).toBeTruthy();
    expect(screen.getAllByText("Raw (hex)")).toHaveLength(3);
  });

  it("renders copy controls for useful node and property values", () => {
    render(<PropertyPanel node={node} />);

    expect(screen.getByRole("button", { name: "Copy Path" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy compatible value" })).toBeTruthy();
    expect(
      screen.getByRole("button", {
        name: "Copy compatible raw hex",
        hidden: true,
      }),
    ).toBeTruthy();
  });

  it("shows a temporary copied state after copying succeeds", async () => {
    vi.useFakeTimers();
    const clipboard = {
      writeText: vi.fn(() => Promise.resolve()),
    };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: clipboard,
    });

    render(<PropertyPanel node={node} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy Path" }));
    });

    expect(clipboard.writeText).toHaveBeenCalledWith("/soc@107c000000");
    expect(screen.getByRole("button", { name: "Copied Path" })).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByRole("button", { name: "Copy Path" })).toBeTruthy();
  });

  it("keeps the normal copy state when copying fails", async () => {
    const clipboard = {
      writeText: vi.fn(() => Promise.reject(new Error("denied"))),
    };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: clipboard,
    });

    render(<PropertyPanel node={node} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy Path" }));
    });

    expect(clipboard.writeText).toHaveBeenCalledWith("/soc@107c000000");
    expect(screen.queryByRole("button", { name: "Copied Path" })).toBeNull();
    expect(screen.getByRole("button", { name: "Copy Path" })).toBeTruthy();
  });
});
