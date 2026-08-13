import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { AddressingReport } from "./models/addressing";
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

const addressingReport: AddressingReport = {
  regions: [
    {
      node_path: "/soc@107c000000/uart@1000",
      kind: "device",
      start: "0x107d001000",
      size: "0x100",
      end: "0x107d0010ff",
    },
  ],
  mappings: [
    {
      node_path: "/soc@107c000000",
      index: 0,
      child_address: "0x0",
      parent_address: "0x107d000000",
      size: "0x100000",
      source_property: "ranges",
    },
  ],
  translations: [
    {
      node_path: "/soc@107c000000/uart@1000",
      bus_address: "0x1000",
      cpu_address: "0x107d001000",
      size: "0x100",
      end: "0x107d0010ff",
      translation_path: [
        {
          bus_node_path: "/soc@107c000000",
          input_address: "0x1000",
          output_address: "0x107d001000",
          mapping_index: 0,
        },
      ],
      warnings: [],
    },
  ],
  warnings: [],
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
    },
  });
}

interface StubApiOptions {
  addressingResponse?: Response | Promise<Response>;
}

function stubApi(options: StubApiOptions = {}): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/devicetree")) {
        return jsonResponse(tree);
      }
      if (url.endsWith("/api/v1/addressing")) {
        return options.addressingResponse ?? jsonResponse(addressingReport);
      }
      return new Response("", { status: 404, statusText: "Not Found" });
    }),
  );
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });

  return { promise, resolve };
}

describe("App", () => {
  it("shows the selected node details after clicking a tree node", async () => {
    stubApi();

    render(<App />);

    expect(await screen.findByRole("tab", { name: "Properties" })).toBeTruthy();
    expect(screen.queryByText("compatible")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "soc@107c000000" }));

    expect(screen.getByText("compatible")).toBeTruthy();
    expect(screen.getByText("[\"simple-bus\"]")).toBeTruthy();
    expect(screen.getByText("73696d706c652d62757300")).toBeTruthy();
  });

  it("selects a search result and expands its ancestor path", async () => {
    stubApi();

    render(<App />);

    expect(await screen.findByRole("tab", { name: "Properties" })).toBeTruthy();
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

  it("shows addressing data for the selected node", async () => {
    stubApi();

    render(<App />);

    expect(await screen.findByRole("tab", { name: "Properties" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Toggle soc@107c000000" }));
    fireEvent.click(screen.getByRole("button", { name: /^uart@1000$/ }));
    fireEvent.click(screen.getByRole("tab", { name: "Addressing" }));

    expect(screen.getByText("Region")).toBeTruthy();
    expect(screen.getByText("device")).toBeTruthy();
    expect(screen.getAllByText("0x107d001000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bus address").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CPU address").length).toBeGreaterThan(0);
    expect(screen.getByText("ranges[0]")).toBeTruthy();
  });

  it("selects and expands a node from the address space map", async () => {
    stubApi();

    render(<App />);

    expect(await screen.findByRole("tab", { name: "Properties" })).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Address Space" }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Select address region /soc@107c000000/uart@1000",
      }),
    );

    expect(screen.getByRole("button", { name: /^uart@1000$/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Properties" }));

    expect(screen.getByText("clock-frequency")).toBeTruthy();
    expect(screen.getByText("[24000000]")).toBeTruthy();
  });

  it("renders the Device Tree before delayed addressing data resolves", async () => {
    const addressing = createDeferred<Response>();
    stubApi({ addressingResponse: addressing.promise });

    render(<App />);

    expect(await screen.findByRole("tab", { name: "Properties" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "soc@107c000000" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "soc@107c000000" }));

    expect(screen.getByText("compatible")).toBeTruthy();
    expect(screen.getByText("[\"simple-bus\"]")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Addressing" }));

    expect(screen.getByText("Loading addressing data...")).toBeTruthy();

    await act(async () => {
      addressing.resolve(jsonResponse(addressingReport));
      await addressing.promise;
    });

    expect(await screen.findByText("Mapping")).toBeTruthy();
    expect(screen.getByText("0x107d000000")).toBeTruthy();
  });
});
