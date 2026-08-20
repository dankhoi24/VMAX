import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddressSpaceMap, buildAddressSpaceEntries } from "./AddressSpaceMap";
import type { MemoryRegion } from "../models/addressing";

afterEach(() => {
  cleanup();
});

function firePointerGestureEvent(
  element: Element,
  type: "pointerdown" | "pointermove" | "pointerup",
  options: { button?: number; clientY: number; pointerId?: number },
) {
  const event = new MouseEvent(type, {
    bubbles: true,
    button: options.button ?? 0,
    buttons: type === "pointerup" ? 0 : 1,
    cancelable: true,
    clientY: options.clientY,
  });

  Object.defineProperty(event, "pointerId", {
    value: options.pointerId ?? 1,
  });

  fireEvent(element, event);
}

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
    expect(regionButtons[1].textContent).toContain("0x1000000000000001");
  });

  it("renders meaningful gaps plus nested and overlapping region metadata", () => {
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
    expect(screen.getByText("0x500 - 0x7ff")).toBeTruthy();
    expect(screen.queryByText("nested")).toBeNull();
    expect(screen.queryByText("overlap")).toBeNull();

    const reserved = screen.getByRole("button", {
      name: "Select address region /reserved-memory/framebuffer@100",
    });
    const dma = screen.getByRole("button", {
      name: "Select address region /soc/dma@300",
    });

    expect(reserved.getAttribute("title")).toContain("Relationship: nested");
    expect(dma.getAttribute("title")).toContain("Relationship: overlap");
    expect(dma.textContent).toContain("0x300");
  });

  it("renders region height proportionally to physical size", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/small@0",
            kind: "device",
            start: "0x0",
            size: "0x100",
            end: "0xff",
          }),
          region({
            node_path: "/large@100",
            kind: "device",
            start: "0x100",
            size: "0x400",
            end: "0x4ff",
          }),
        ]}
      />,
    );

    const small = screen.getByRole("button", {
      name: "Select address region /small@0",
    });
    const large = screen.getByRole("button", {
      name: "Select address region /large@100",
    });

    const smallGeometry = small.querySelector(".address-space-region-geometry");
    const largeGeometry = large.querySelector(".address-space-region-geometry");

    expect(parseFloat((largeGeometry as HTMLElement).style.height)).toBeGreaterThan(
      parseFloat((smallGeometry as HTMLElement).style.height),
    );
  });

  it("zooms with controls and can fit all regions", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    expect(screen.getByText("span 0x100000")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "+" }));
    expect(screen.getByText("span 0x80000")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Fit All" }));
    expect(screen.getByText("span 0x100000")).toBeTruthy();
  });

  it("pans with the mouse wheel in default mode", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Default" }).getAttribute(
        "aria-pressed",
      ),
    ).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "+" }));

    fireEvent.wheel(screen.getByLabelText("CPU Physical Address Space"), {
      deltaY: 130,
      clientY: 260,
    });

    expect(screen.getByText("span 0x80000")).toBeTruthy();
    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0x60000",
    );
  });

  it("does not pan the viewport by dragging in default mode", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "+" }));

    const plot = screen.getByLabelText("CPU Physical Address Space");
    firePointerGestureEvent(plot, "pointerdown", {
      button: 0,
      clientY: 260,
      pointerId: 1,
    });
    firePointerGestureEvent(plot, "pointermove", {
      clientY: 390,
      pointerId: 1,
    });
    firePointerGestureEvent(plot, "pointerup", {
      clientY: 390,
      pointerId: 1,
    });

    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0x40000",
    );
  });

  it("pans the viewport by dragging in hand mode", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "+" }));
    fireEvent.click(screen.getByRole("button", { name: "Hand" }));

    const plot = screen.getByLabelText("CPU Physical Address Space");
    firePointerGestureEvent(plot, "pointerdown", {
      button: 0,
      clientY: 260,
      pointerId: 1,
    });
    firePointerGestureEvent(plot, "pointermove", {
      clientY: 390,
      pointerId: 1,
    });
    firePointerGestureEvent(plot, "pointerup", {
      clientY: 390,
      pointerId: 1,
    });

    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0x20000",
    );
  });

  it("zooms around the pointer anchor with the mouse wheel in hand mode", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    const defaultMode = screen.getByRole("button", { name: "Default" });
    const handMode = screen.getByRole("button", { name: "Hand" });

    expect(defaultMode.getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(handMode);

    expect(handMode.getAttribute("aria-pressed")).toBe("true");

    const plot = screen.getByLabelText("CPU Physical Address Space");
    fireEvent.wheel(plot, {
      clientY: 260,
      deltaY: -120,
    });

    expect(screen.getByText("span 0x80000")).toBeTruthy();
    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0x40000",
    );
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
    expect(
      screen.getByRole("button", {
        name: "Select address region /soc/uart@1000",
      }).className,
    ).toContain("address-space-region-hitbox-selected");
  });

  it("refocuses the same selected node when focusRequest changes", () => {
    const regions = [
      region({
        node_path: "/memory@0",
        kind: "ram",
        start: "0x0",
        size: "0x100000",
        end: "0xfffff",
      }),
      region({
        node_path: "/soc/uart@100000",
        kind: "device",
        start: "0x100000",
        size: "0x100",
        end: "0x1000ff",
      }),
    ];
    const { rerender } = render(
      <AddressSpaceMap
        regions={regions}
        selectedNodePath="/soc/uart@100000"
        focusRequest={1}
      />,
    );

    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0xffb00",
    );

    fireEvent.click(screen.getByRole("button", { name: "Fit All" }));

    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0x0",
    );

    rerender(
      <AddressSpaceMap
        regions={regions}
        selectedNodePath="/soc/uart@100000"
        focusRequest={2}
      />,
    );

    expect(screen.getByLabelText("Visible address range").textContent).toContain(
      "0xffb00",
    );
  });

  it("uses level-of-detail modes for dense labels", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/tiny@0",
            kind: "device",
            start: "0x0",
            size: "0x1",
            end: "0x0",
          }),
          region({
            node_path: "/large@100000",
            kind: "device",
            start: "0x100000",
            size: "0x100000",
            end: "0x1fffff",
          }),
        ]}
      />,
    );

    const tiny = screen.getByRole("button", {
      name: "Select address region /tiny@0",
    });
    const large = screen.getByRole("button", {
      name: "Select address region /large@100000",
    });

    expect(tiny.className).toContain("address-space-region-hitbox-marker");
    expect(tiny.querySelector(".address-space-region-label")).toBeNull();
    expect(tiny.querySelector(".address-space-region-callout")).toBeTruthy();
    expect(large.className).toContain("address-space-region-hitbox-full");
    expect(large.querySelector(".address-space-region-label code")).toBeTruthy();
  });

  it("uses line-only markers for tiny gaps", () => {
    const { container } = render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/left@0",
            kind: "device",
            start: "0x0",
            size: "0x1000",
            end: "0xfff",
          }),
          region({
            node_path: "/right@1010",
            kind: "device",
            start: "0x1010",
            size: "0x200000",
            end: "0x200fff",
          }),
        ]}
      />,
    );

    const tinyGap = container.querySelector(".address-space-gap-band-marker");

    expect(tinyGap).toBeTruthy();
    expect(tinyGap?.textContent).toBe("");
  });

  it("clusters dense marker regions and drills into the cluster", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/device@0",
            kind: "device",
            start: "0x0",
            size: "0x1",
            end: "0x0",
          }),
          region({
            node_path: "/device@100",
            kind: "device",
            start: "0x100",
            size: "0x1",
            end: "0x100",
          }),
          region({
            node_path: "/device@200",
            kind: "device",
            start: "0x200",
            size: "0x1",
            end: "0x200",
          }),
          region({
            node_path: "/memory@100000",
            kind: "ram",
            start: "0x100000",
            size: "0x1000",
            end: "0x100fff",
          }),
        ]}
      />,
    );

    const cluster = screen.getByRole("button", {
      name: "Zoom into 3 address regions",
    });

    expect(cluster.textContent).toBe("+3");

    fireEvent.click(cluster);

    expect(screen.getByText("span 0x40400")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Zoom into 3 address regions",
      }),
    );

    expect(screen.getByText("span 0x10100")).toBeTruthy();
  });

  it("expands inseparable clusters into selectable members", () => {
    const onSelectRegion = vi.fn();

    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/soc/foo@1000",
            kind: "device",
            start: "0x1000",
            size: "0x1",
            end: "0x1000",
          }),
          region({
            node_path: "/soc/bar@1000",
            kind: "device",
            start: "0x1000",
            size: "0x1",
            end: "0x1000",
          }),
          region({
            node_path: "/soc/baz@1000",
            kind: "device",
            start: "0x1000",
            size: "0x1",
            end: "0x1000",
          }),
          region({
            node_path: "/memory@100000",
            kind: "ram",
            start: "0x100000",
            size: "0x1000",
            end: "0x100fff",
          }),
        ]}
        onSelectRegion={onSelectRegion}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Zoom into 3 address regions",
      }),
    );

    expect(
      screen.getByRole("group", {
        name: "3 clustered address regions",
      }),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /\/soc\/bar@1000/ }));

    expect(onSelectRegion).toHaveBeenCalledWith("/soc/bar@1000");
  });

  it("shows selected resource focus controls for multi-region nodes", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/soc/device@0",
            kind: "device",
            start: "0x100000",
            size: "0x100",
            end: "0x1000ff",
          }),
          region({
            node_path: "/soc/device@0",
            kind: "device",
            start: "0x90000000",
            size: "0x100",
            end: "0x900000ff",
          }),
        ]}
        selectedNodePath="/soc/device@0"
      />,
    );

    const resource0 = screen.getByRole("button", { name: "Resource 0" });
    const resource1 = screen.getByRole("button", { name: "Resource 1" });
    const fitNode = screen.getByRole("button", { name: "Fit Node" });

    expect(resource0.className).toContain("address-space-resource-button-active");

    fireEvent.click(resource1);

    expect(resource1.className).toContain("address-space-resource-button-active");

    fireEvent.click(fitNode);

    expect(fitNode.className).toContain("address-space-resource-button-active");
  });

  it("preserves unknown-size markers without fabricating covered gaps", () => {
    const entries = buildAddressSpaceEntries([
      region({
        node_path: "/unknown@1000",
        kind: "device",
        start: "0x1000",
        size: null,
        end: null,
      }),
      region({
        node_path: "/known@2000",
        kind: "device",
        start: "0x2000",
        size: "0x100",
        end: "0x20ff",
      }),
    ]);

    expect(
      entries.some(
        (entry) =>
          entry.entryKind === "unknown" &&
          entry.region.node_path === "/unknown@1000",
      ),
    ).toBe(true);
    expect(
      entries.some(
        (entry) =>
          entry.entryKind === "region" &&
          entry.region.node_path === "/known@2000",
      ),
    ).toBe(true);
    expect(
      entries.some(
        (entry) =>
          entry.entryKind === "gap" &&
          entry.start === 0n &&
          entry.end === 0x1fffn,
      ),
    ).toBe(false);
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

  it("makes address overlays non-interactive in hand mode", () => {
    render(
      <AddressSpaceMap
        regions={[
          region({
            node_path: "/memory@0",
            kind: "ram",
            start: "0x0",
            size: "0x100000",
            end: "0xfffff",
          }),
        ]}
      />,
    );

    const handModeButton = screen.getByRole("button", { name: "Hand" });
    fireEvent.click(handModeButton);

    const plot = screen.getByLabelText("CPU Physical Address Space");

    // Check that plot has the correct class for hand mode
    expect(plot.className).toContain("address-space-plot-hand");
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
