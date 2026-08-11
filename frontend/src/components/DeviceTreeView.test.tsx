import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
    renderDeviceTreeView();

    expect(screen.getByText("/")).toBeTruthy();
    expect(screen.getByText("soc")).toBeTruthy();
    expect(screen.getByText("chosen")).toBeTruthy();
    expect(screen.getByText("4 nodes")).toBeTruthy();
  });

  it("does not render descendants of collapsed child nodes by default", () => {
    renderDeviceTreeView();

    expect(screen.queryByText("uart@1000")).toBeNull();
  });

  it("expands and collapses child node descendants", () => {
    renderDeviceTreeView();

    const socToggle = screen.getByRole("button", { name: "Toggle soc" });

    fireEvent.click(socToggle);
    expect(screen.getByText("uart@1000")).toBeTruthy();

    fireEvent.click(socToggle);
    expect(screen.queryByText("uart@1000")).toBeNull();
  });

  it("selects nodes through the node label", () => {
    const onSelectNode = vi.fn();

    renderDeviceTreeView("/soc", onSelectNode);

    const socTreeItem = screen.getByText("soc").closest('[role="treeitem"]');
    expect(socTreeItem?.getAttribute("aria-selected")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "chosen" }));

    expect(onSelectNode).toHaveBeenCalledWith(tree.children[1]);
  });
});

function renderDeviceTreeView(
  selectedPath: string | null = tree.path,
  onSelectNode: (node: DeviceTreeNode) => void = () => undefined,
) {
  function DeviceTreeViewHarness() {
    const [expandedPaths, setExpandedPaths] = useState<Set<string>>(
      () => new Set([tree.path]),
    );

    const toggleNode = (path: string) => {
      setExpandedPaths((current) => {
        const next = new Set(current);
        if (next.has(path)) {
          next.delete(path);
        } else {
          next.add(path);
        }
        return next;
      });
    };

    return (
      <DeviceTreeView
        root={tree}
        nodeCount={4}
        expandedPaths={expandedPaths}
        selectedPath={selectedPath}
        onToggleNode={toggleNode}
        onSelectNode={onSelectNode}
      />
    );
  }

  render(<DeviceTreeViewHarness />);
}
