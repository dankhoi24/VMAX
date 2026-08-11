import { describe, expect, it } from "vitest";

import {
  getAncestorPaths,
  searchDeviceTree,
} from "./devicetreeSearch";
import type { DeviceTreeNode } from "../models/devicetree";

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
      properties: [
        {
          name: "compatible",
          kind: "string_list",
          value: ["simple-bus"],
          raw_hex: "73696d706c652d62757300",
        },
      ],
      children: [
        {
          id: "/soc/serial@1000",
          name: "serial",
          full_name: "serial@1000",
          path: "/soc/serial@1000",
          unit_address: "1000",
          parent_path: "/soc",
          properties: [
            {
              name: "compatible",
              kind: "string_list",
              value: ["arm,pl011"],
              raw_hex: "61726d2c706c30313100",
            },
            {
              name: "clock-frequency",
              kind: "cells",
              value: [24000000],
              raw_hex: "016e3600",
            },
          ],
          children: [],
        },
      ],
    },
  ],
};

describe("devicetree search", () => {
  it("matches node paths, names, and full names", () => {
    const results = searchDeviceTree(tree, "serial");

    expect(results.map((result) => result.node.path)).toEqual([
      "/soc/serial@1000",
    ]);
    expect(results[0].matches).toEqual(["path", "node"]);
  });

  it("matches compatible values", () => {
    const results = searchDeviceTree(tree, "pl011");

    expect(results.map((result) => result.node.path)).toEqual([
      "/soc/serial@1000",
    ]);
    expect(results[0].matches).toEqual(["compatible"]);
  });

  it("matches property names", () => {
    const results = searchDeviceTree(tree, "clock-frequency");

    expect(results.map((result) => result.node.path)).toEqual([
      "/soc/serial@1000",
    ]);
    expect(results[0].matches).toEqual(["property"]);
  });

  it("returns no results for blank queries", () => {
    expect(searchDeviceTree(tree, "   ")).toEqual([]);
  });

  it("returns ancestor paths needed to reveal a selected result", () => {
    expect(getAncestorPaths("/soc/serial@1000")).toEqual(["/", "/soc"]);
    expect(getAncestorPaths("/")).toEqual(["/"]);
  });
});
