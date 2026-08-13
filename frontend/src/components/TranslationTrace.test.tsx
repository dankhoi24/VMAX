import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TranslationTrace } from "./TranslationTrace";
import type { TranslatedAddressRange } from "../models/addressing";

afterEach(() => {
  cleanup();
});

describe("TranslationTrace", () => {
  it("renders multiple bus translation steps in order", () => {
    render(
      <TranslationTrace
        translation={{
          node_path: "/bus-b/bus-a/device@100",
          bus_address: "0x100",
          cpu_address: "0x107d020100",
          size: "0x10",
          end: "0x107d02010f",
          translation_path: [
            {
              bus_node_path: "/bus-b/bus-a",
              input_address: "0x100",
              output_address: "0x20100",
              mapping_index: 1,
            },
            {
              bus_node_path: "/bus-b",
              input_address: "0x20100",
              output_address: "0x107d020100",
              mapping_index: 0,
            },
          ],
          warnings: [],
        }}
      />,
    );

    expect(screen.getByLabelText("Address translation trace")).toBeTruthy();
    expect(screen.getByText("Bus address")).toBeTruthy();
    expect(screen.getByText("/bus-b/bus-a")).toBeTruthy();
    expect(screen.getByText("ranges[1]")).toBeTruthy();
    expect(screen.getByText("/bus-b")).toBeTruthy();
    expect(screen.getByText("ranges[0]")).toBeTruthy();
    expect(screen.getByText("CPU address")).toBeTruthy();
    expect(screen.getAllByText("0x107d020100").length).toBeGreaterThan(0);
  });

  it("renders identity mapping steps", () => {
    render(
      <TranslationTrace
        translation={{
          node_path: "/soc/device@1000",
          bus_address: "0x1000",
          cpu_address: "0x1000",
          size: "0x100",
          end: "0x10ff",
          translation_path: [
            {
              bus_node_path: "/soc",
              input_address: "0x1000",
              output_address: "0x1000",
              mapping_index: null,
            },
          ],
          warnings: [],
        }}
      />,
    );

    expect(screen.getByText("identity")).toBeTruthy();
    expect(screen.getAllByText("0x1000").length).toBeGreaterThan(1);
  });

  it("renders a direct CPU-visible resource when no bus steps exist", () => {
    render(
      <TranslationTrace
        translation={translation({
          bus_address: "0xfffffffffffff000",
          cpu_address: "0xfffffffffffff000",
          end: "0xffffffffffffffff",
          translation_path: [],
        })}
      />,
    );

    expect(screen.getByText("cpu-visible")).toBeTruthy();
    expect(screen.getAllByText("0xfffffffffffff000").length).toBeGreaterThan(1);
  });

  it("renders unresolved translations without fabricating a CPU address", () => {
    render(
      <TranslationTrace
        translation={translation({
          bus_address: "0x2000",
          cpu_address: null,
          end: null,
          translation_path: [],
        })}
      />,
    );

    expect(screen.getByText("Unresolved")).toBeTruthy();
    expect(screen.getByText("-")).toBeTruthy();
    expect(screen.queryByText("CPU address")).toBeNull();
  });
});

function translation(
  overrides: Partial<TranslatedAddressRange>,
): TranslatedAddressRange {
  return {
    node_path: "/device@0",
    bus_address: "0x0",
    cpu_address: "0x0",
    size: "0x1000",
    end: "0xfff",
    translation_path: [],
    warnings: [],
    ...overrides,
  };
}
