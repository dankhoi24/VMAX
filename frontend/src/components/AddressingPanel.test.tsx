import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AddressingPanel } from "./AddressingPanel";
import type { AddressingReport } from "../models/addressing";
import type { DeviceTreeNode } from "../models/devicetree";

afterEach(() => {
  cleanup();
});

const uartNode: DeviceTreeNode = {
  id: "/soc/uart@1000",
  name: "uart",
  full_name: "uart@1000",
  path: "/soc/uart@1000",
  unit_address: "1000",
  parent_path: "/soc",
  properties: [],
  children: [],
};

const socNode: DeviceTreeNode = {
  id: "/soc",
  name: "soc",
  full_name: "soc",
  path: "/soc",
  unit_address: null,
  parent_path: "/",
  properties: [],
  children: [uartNode],
};

const report: AddressingReport = {
  regions: [
    {
      node_path: "/soc/uart@1000",
      kind: "device",
      start: "0x107d001000",
      size: "0x100",
      end: "0x107d0010ff",
    },
    {
      node_path: "/soc/uart@1000",
      kind: "device",
      start: "0x107d002000",
      size: "0x80",
      end: "0x107d00207f",
    },
  ],
  mappings: [
    {
      node_path: "/soc",
      index: 0,
      child_address: "0x0",
      parent_address: "0x107d000000",
      size: "0x100000",
      source_property: "ranges",
    },
  ],
  translations: [
    {
      node_path: "/soc/uart@1000",
      bus_address: "0x1000",
      cpu_address: "0x107d001000",
      size: "0x100",
      end: "0x107d0010ff",
      translation_path: [
        {
          bus_node_path: "/soc",
          input_address: "0x1000",
          output_address: "0x107d001000",
          mapping_index: 0,
        },
      ],
      warnings: [],
    },
    {
      node_path: "/soc/uart@1000",
      bus_address: "0x2000",
      cpu_address: "0x107d002000",
      size: "0x80",
      end: "0x107d00207f",
      translation_path: [],
      warnings: [],
    },
  ],
  warnings: [
    {
      code: "NON_MEMORY_REG_SEMANTICS",
      node_path: "/cpus/cpu@0",
      message: "Size-less reg resource is not treated as an address range",
    },
  ],
};

describe("AddressingPanel", () => {
  it("renders an empty state for nodes without addressing data", () => {
    render(
      <AddressingPanel
        node={{ ...uartNode, path: "/chosen", id: "/chosen" }}
        state={{ status: "success", report }}
      />,
    );

    expect(
      screen.getByText("No address resources described for this node."),
    ).toBeTruthy();
  });

  it("renders memory regions and translations for the selected node", () => {
    render(<AddressingPanel node={uartNode} state={{ status: "success", report }} />);

    expect(screen.getByText("Region")).toBeTruthy();
    expect(screen.getAllByText("device")).toHaveLength(2);
    expect(screen.getAllByText("0x107d001000").length).toBeGreaterThan(0);
    expect(screen.queryByText("0x2000")).toBeNull();
    expect(screen.getAllByText("Resource 0").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: "Resource 1" })).toBeTruthy();
    expect(screen.getByText("/soc")).toBeTruthy();
    expect(screen.getByText("ranges[0]")).toBeTruthy();
    expect(screen.getAllByText("Bus address").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CPU address").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("tab", { name: "Resource 1" }));

    expect(screen.getAllByText("0x107d002000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("0x2000").length).toBeGreaterThan(0);
  });

  it("renders mappings for the selected bus node", () => {
    render(<AddressingPanel node={socNode} state={{ status: "success", report }} />);

    expect(screen.getByText("Mapping")).toBeTruthy();
    expect(screen.getByText("ranges[0]")).toBeTruthy();
    expect(screen.getByText("0x107d000000")).toBeTruthy();
    expect(screen.getByText("0x100000")).toBeTruthy();
  });

  it("renders semantic warnings for the selected node", () => {
    render(
      <AddressingPanel
        node={{
          ...uartNode,
          id: "/cpus/cpu@0",
          path: "/cpus/cpu@0",
          full_name: "cpu@0",
        }}
        state={{ status: "success", report }}
      />,
    );

    expect(screen.getByText("Warnings")).toBeTruthy();
    expect(screen.getByText("NON_MEMORY_REG_SEMANTICS")).toBeTruthy();
    expect(
      screen.getByText("Size-less reg resource is not treated as an address range"),
    ).toBeTruthy();
  });

  it("renders loading and error states", () => {
    const { rerender } = render(
      <AddressingPanel node={uartNode} state={{ status: "loading" }} />,
    );

    expect(screen.getByText("Loading addressing data...")).toBeTruthy();

    rerender(
      <AddressingPanel
        node={uartNode}
        state={{
          status: "error",
          message: "Failed",
          detail: ["bad.dtb"],
        }}
      />,
    );

    expect(screen.getByText("Unable to load addressing data")).toBeTruthy();
    expect(screen.getByText("bad.dtb")).toBeTruthy();
  });
});
