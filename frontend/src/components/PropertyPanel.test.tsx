import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PropertyPanel } from "./PropertyPanel";
import type { DeviceTreeNode } from "../models/devicetree";

afterEach(cleanup);

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
    expect(screen.getByText("[\"simple-bus\"]")).toBeTruthy();
    expect(screen.getByText("73696d706c652d62757300")).toBeTruthy();

    expect(screen.getByText("#address-cells")).toBeTruthy();
    expect(screen.getAllByText("cells")).toHaveLength(2);
    expect(screen.getByText("[2]")).toBeTruthy();
    expect(screen.getByText("00000002")).toBeTruthy();

    expect(screen.getByText("ranges")).toBeTruthy();
    expect(screen.getByText("[0,0,1,0]")).toBeTruthy();
    expect(screen.getByText("00000000000000000000000100000000")).toBeTruthy();
  });
});
