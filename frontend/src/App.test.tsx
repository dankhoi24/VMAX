import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { DeviceTreeResponse } from "./models/devicetree";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const tree: DeviceTreeResponse = {
  node_count: 3,
  root: {
    id: "/",
    name: "/",
    full_name: "/",
    path: "/",
    unit_address: null,
    parent_path: null,
    properties: [],
    children: [
      {
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
        ],
        children: [
          {
            id: "/soc@107c000000/uart@1000",
            name: "uart",
            full_name: "uart@1000",
            path: "/soc@107c000000/uart@1000",
            unit_address: "1000",
            parent_path: "/soc@107c000000",
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
  },
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
  });
}

describe("App", () => {
  it("shows the selected node details after clicking a tree node", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(tree)));

    render(<App />);

    expect(await screen.findByText("0 properties")).toBeTruthy();
    expect(screen.queryByText("compatible")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "soc@107c000000" }));

    expect(screen.getByText("compatible")).toBeTruthy();
    expect(screen.getByText("[\"simple-bus\"]")).toBeTruthy();
    expect(screen.getByText("73696d706c652d62757300")).toBeTruthy();
  });

  it("selects a search result and expands its ancestor path", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(tree)));

    render(<App />);

    expect(await screen.findByText("0 properties")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^uart@1000$/ })).toBeNull();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search Device Tree" }), {
      target: { value: "pl011" },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: /\/soc@107c000000\/uart@1000/,
      }),
    );

    expect(screen.getByRole("button", { name: /^uart@1000$/ })).toBeTruthy();
    expect(screen.getByText("clock-frequency")).toBeTruthy();
    expect(screen.getByText("[24000000]")).toBeTruthy();
  });
});
