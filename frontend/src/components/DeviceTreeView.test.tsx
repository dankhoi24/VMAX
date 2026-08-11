import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DeviceTreeView } from "./DeviceTreeView";
import type { DeviceTreeNode } from "../models/devicetree";

afterEach(cleanup);

const tree: DeviceTreeNode = {
  id: "/",
  name: "/",
  full_name: "/",
  path: "/",
  unit_address: null,
  parent_path: null,
  properties: [],
  children: [
    {
      id: "/soc",
      name: "soc",
      full_name: "soc",
      path: "/soc",
      unit_address: null,
      parent_path: "/",
      properties: [],
      children: [
        {
          id: "/soc/uart@1000",
          name: "uart",
          full_name: "uart@1000",
          path: "/soc/uart@1000",
          unit_address: "1000",
          parent_path: "/soc",
          properties: [],
          children: [],
        },
      ],
    },
    {
      id: "/chosen",
      name: "chosen",
      full_name: "chosen",
      path: "/chosen",
      unit_address: null,
      parent_path: "/",
      properties: [],
      children: [],
    },
  ],
};

describe("DeviceTreeView", () => {
  it("renders root and immediate children by default", () => {
    render(<DeviceTreeView root={tree} nodeCount={4} />);

    expect(screen.getByText("/")).toBeTruthy();
    expect(screen.getByText("soc")).toBeTruthy();
    expect(screen.getByText("chosen")).toBeTruthy();
    expect(screen.getByText("4 nodes")).toBeTruthy();
  });

  it("does not render descendants of collapsed child nodes by default", () => {
    render(<DeviceTreeView root={tree} nodeCount={4} />);

    expect(screen.queryByText("uart@1000")).toBeNull();
  });

  it("expands and collapses child node descendants", () => {
    render(<DeviceTreeView root={tree} nodeCount={4} />);

    const socToggle = screen.getByRole("button", { name: "Toggle soc" });

    fireEvent.click(socToggle);
    expect(screen.getByText("uart@1000")).toBeTruthy();

    fireEvent.click(socToggle);
    expect(screen.queryByText("uart@1000")).toBeNull();
  });
});
