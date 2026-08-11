import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SearchBox } from "./SearchBox";
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
          id: "/soc/uart@1000",
          name: "uart",
          full_name: "uart@1000",
          path: "/soc/uart@1000",
          unit_address: "1000",
          parent_path: "/soc",
          properties: [
            {
              name: "compatible",
              kind: "string_list",
              value: ["arm,pl011"],
              raw_hex: "61726d2c706c30313100",
            },
          ],
          children: [],
        },
      ],
    },
  ],
};

describe("SearchBox", () => {
  it("renders local search results for a query", () => {
    render(<SearchBox root={tree} onSelectResult={() => undefined} />);

    expect(
      screen.getByPlaceholderText("Search nodes, paths, properties..."),
    ).toBeTruthy();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search Device Tree" }), {
      target: { value: "uart" },
    });

    expect(screen.getByText("1 match")).toBeTruthy();
    expect(screen.getByText("uart@1000")).toBeTruthy();
    expect(screen.getByText("/soc/uart@1000")).toBeTruthy();
    expect(screen.getByText("path")).toBeTruthy();
    expect(screen.getByText("node")).toBeTruthy();
  });

  it("selects a result when clicked", () => {
    const onSelectResult = vi.fn();
    render(<SearchBox root={tree} onSelectResult={onSelectResult} />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search Device Tree" }), {
      target: { value: "pl011" },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: /\/soc\/uart@1000/,
      }),
    );

    expect(onSelectResult).toHaveBeenCalledWith(tree.children[0].children[0]);
  });

  it("closes results after selecting and reopens them on input focus", () => {
    render(<SearchBox root={tree} onSelectResult={() => undefined} />);

    const input = screen.getByRole("searchbox", { name: "Search Device Tree" });
    fireEvent.change(input, {
      target: { value: "pl011" },
    });

    expect(screen.getByText("/soc/uart@1000")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", {
        name: /\/soc\/uart@1000/,
      }),
    );

    expect(screen.queryByText("/soc/uart@1000")).toBeNull();

    fireEvent.focus(input);

    expect(screen.getByText("/soc/uart@1000")).toBeTruthy();
  });

  it("renders no matches for unmatched queries", () => {
    render(<SearchBox root={tree} onSelectResult={() => undefined} />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search Device Tree" }), {
      target: { value: "i2c" },
    });

    expect(screen.getByText("No matches")).toBeTruthy();
  });
});
