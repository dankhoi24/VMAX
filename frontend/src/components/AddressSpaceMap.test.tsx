import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddressSpaceMap, buildAddressSpaceEntries } from "./AddressSpaceMap";
import type { MemoryRegion } from "../models/addressing";

afterEach(() => {
  cleanup();
});

describe("AddressSpaceMap", () => {
  it("sorts address regions with BigInt precision", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/device@1000000000000001",
            kind: "device",
            start: "0x1000000000000001",
            size: "0x10",
            end: "0x1000000000000010",
          }),
          region({
            node_path: "/memory@1000000000000000",
            kind: "ram",
            start: "0x1000000000000000",
            size: "0x1",
            end: "0x1000000000000000",
          }),
        ]}
        onSelectRegion={() => undefined}
      />,
    );

    const regionButtons = screen.getAllByRole("button", {
      name: /Select address region/,
    });

    expect(regionButtons[0].textContent).toContain(
      "/memory@1000000000000000",
    );
    expect(regionButtons[1].textContent).toContain(
      "/device@1000000000000001",
    );
    expect(screen.getByText("0x1000000000000001")).toBeTruthy();
  });

  it("renders meaningful gaps plus nested and overlapping regions", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x400",
            end: "0x3ff",
          }),
          region({
            node_path: "/reserved-memory/framebuffer@100",
            kind: "reserved",
            start: "0x100",
            size: "0x100",
            end: "0x1ff",
          }),
          region({
            node_path: "/soc/dma@300",
            kind: "device",
            start: "0x300",
            size: "0x200",
            end: "0x4ff",
          }),
          region({
            node_path: "/soc/uart@800",
            kind: "device",
            start: "0x800",
            size: "0x100",
            end: "0x8ff",
          }),
        ]}
      />,
    );

    expect(screen.getByLabelText("CPU Physical Address Space")).toBeTruthy();
    expect(screen.getByText("nested")).toBeTruthy();
    expect(screen.getByText("overlap")).toBeTruthy();
    expect(screen.getByText("0x500")).toBeTruthy();
    expect(screen.getByText("0x7ff")).toBeTruthy();
    expect(screen.getAllByText("0x300").length).toBeGreaterThan(0);
  });

  it("selects a Device Tree node when a region is clicked", () => {
    const onSelectRegion = vi.fn();

    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/soc/uart@1000",
            kind: "device",
            start: "0x107d001000",
            size: "0x100",
            end: "0x107d0010ff",
          }),
        ]}
        selectedNodePath="/soc/uart@1000"
        onSelectRegion={onSelectRegion}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Select address region /soc/uart@1000",
      }),
    );

    expect(onSelectRegion).toHaveBeenCalledWith("/soc/uart@1000");
    expect(screen.getByText("selected")).toBeTruthy();
  });

  it("builds entries without fabricating gaps inside covered ranges", () => {
    const entries = buildAddressSpaceEntries([
      region({
        node_path: "/memory@0",
        kind: "ram",
        start: "0x0",
        size: "0x1000",
        end: "0xfff",
      }),
      region({
        node_path: "/reserved-memory/camera@400",
        kind: "reserved",
        start: "0x400",
        size: "0x100",
        end: "0x4ff",
      }),
    ]);

    expect(entries).toHaveLength(2);
    expect(entries[0].entryKind).toBe("region");
    expect(entries[1]).toMatchObject({
      entryKind: "region",
      relation: "nested",
    });
  });
});

function region(overrides: Partial<MemoryRegion>): MemoryRegion {
  return {
    node_path: "/node@0",
    kind: "device",
    start: "0x0",
    size: "0x1",
    end: "0x0",
    ...overrides,
  };
}
