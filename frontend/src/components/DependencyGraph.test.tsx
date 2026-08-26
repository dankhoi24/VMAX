import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildDependencyGraph } from "../graph/dependencyGraph";
import type {
  DependencyRuntimeInterrupt,
  DeviceDependency,
  DeviceDependencyView,
} from "../models/dependency";
import { DependencyGraph } from "./DependencyGraph";

const runtimeIrq214: DependencyRuntimeInterrupt = {
  irq: 214,
  counts: [0, 4291, 0, 0],
  controller: "GICv3",
  hardware_irq: 182,
  trigger: "Level",
  actions: ["imr"],
  total_count: 4291,
  source_path: "/proc/interrupts",
  metadata: [],
};

const clockDependency: DeviceDependency = {
  kind: "clock",
  consumer_dt_path: "/soc/imr@e6260000",
  provider_dt_path: "/soc/cpg@e6150000",
  provider_phandle: 12,
  entry_index: 0,
  name: "fck",
  specifier_cells: [12, 4],
  source_property: "clocks",
  static_resolution: "resolved",
  evidence: [],
  interrupt_resolution: null,
  interrupt_match_method: null,
  runtime_interrupt: null,
  runtime_candidates: [],
  interrupt_warnings: [],
};

const interruptDependency: DeviceDependency = {
  ...clockDependency,
  kind: "interrupt",
  provider_dt_path: "/soc/interrupt-controller@f1000000",
  provider_phandle: 1,
  name: null,
  specifier_cells: [0, 150, 4],
  source_property: "interrupts",
  interrupt_resolution: "resolved",
  interrupt_match_method: "controller_hardware_irq",
  runtime_interrupt: runtimeIrq214,
  runtime_candidates: [runtimeIrq214],
};

const imrView: DeviceDependencyView = {
  dt_node_path: "/soc/imr@e6260000",
  dependencies: [clockDependency, interruptDependency],
};

describe("DependencyGraph", () => {
  it("renders focus device, providers, and runtime IRQ topology", () => {
    const graph = buildDependencyGraph(imrView);

    const { container } = render(<DependencyGraph graph={graph} />);

    const panel = screen.getByLabelText("Dependency graph");
    expect(panel.textContent).toContain("Focus Graph");
    expect(panel.textContent).toContain(
      "Static dependency: consumer -> provider · Runtime mapping: provider -> IRQ",
    );
    expect(panel.textContent).toContain("imr@e6260000");
    expect(panel.textContent).toContain("cpg@e6150000");
    expect(panel.textContent).toContain("interrupt-controller@f1000000");
    expect(panel.textContent).toContain("Linux IRQ214");
    expect(panel.textContent).toContain("CLOCK");
    expect(panel.textContent).toContain("HWIRQ 182");
    expect(
      container.querySelector(
        '.dependency-graph-edge-resolved path[marker-end="url(#dependency-arrow-resolved)"]',
      ),
    ).toBeTruthy();
  });

  it("selects a provider node when it has a dependency view", () => {
    const onSelectDtPath = vi.fn();
    const graph = buildDependencyGraph(imrView, [
      imrView,
      {
        dt_node_path: "/soc/cpg@e6150000",
        dependencies: [],
      },
    ]);

    render(
      <DependencyGraph graph={graph} onSelectDtPath={onSelectDtPath} />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Select dependency graph node cpg@e6150000",
      }),
    );

    expect(onSelectDtPath).toHaveBeenCalledWith("/soc/cpg@e6150000");
  });
});
