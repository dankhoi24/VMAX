import { describe, expect, it } from "vitest";

import type {
  DependencyRuntimeInterrupt,
  DeviceDependency,
  DeviceDependencyView,
} from "../models/dependency";
import { buildDependencyGraph } from "./dependencyGraph";

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

const iommuDependency: DeviceDependency = {
  ...clockDependency,
  kind: "iommu",
  provider_dt_path: "/soc/ipmmu@e6740000",
  provider_phandle: 30,
  entry_index: 0,
  name: null,
  specifier_cells: [3],
  source_property: "iommus",
};

const interruptDependency: DeviceDependency = {
  ...clockDependency,
  kind: "interrupt",
  provider_dt_path: "/soc/interrupt-controller@f1000000",
  provider_phandle: 1,
  specifier_cells: [0, 150, 4],
  source_property: "interrupts",
  interrupt_resolution: "resolved",
  interrupt_match_method: "controller_hardware_irq",
  runtime_interrupt: runtimeIrq214,
  runtime_candidates: [runtimeIrq214],
};

const imrView: DeviceDependencyView = {
  dt_node_path: "/soc/imr@e6260000",
  dependencies: [clockDependency, iommuDependency, interruptDependency],
};

describe("buildDependencyGraph", () => {
  it("builds a focus graph with providers and runtime IRQ as provider child", () => {
    const graph = buildDependencyGraph(imrView);

    expect(graph.nodes.map((node) => node.label)).toEqual(
      expect.arrayContaining([
        "imr@e6260000",
        "cpg@e6150000",
        "ipmmu@e6740000",
        "interrupt-controller@f1000000",
        "Linux IRQ214",
      ]),
    );
    expect(graph.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: "dt:/soc/imr@e6260000",
          target: "dt:/soc/cpg@e6150000",
          kind: "clock",
          relation: "static_dependency",
          resolution: "resolved",
        }),
        expect.objectContaining({
          source: "dt:/soc/interrupt-controller@f1000000",
          target: "irq:214",
          kind: "interrupt",
          relation: "runtime_mapping",
          resolution: "resolved",
          label: "HWIRQ 182",
        }),
      ]),
    );
  });

  it("does not create duplicate IRQ nodes from resolved candidates", () => {
    const graph = buildDependencyGraph(imrView);

    expect(graph.nodes.filter((node) => node.id === "irq:214")).toHaveLength(1);
    expect(
      graph.edges.filter(
        (edge) => edge.relation === "runtime_mapping" && edge.target === "irq:214",
      ),
    ).toHaveLength(1);
  });

  it("deduplicates shared providers while preserving separate dependency edges", () => {
    const secondClock: DeviceDependency = {
      ...clockDependency,
      entry_index: 1,
      name: "bus",
      specifier_cells: [13, 0],
    };
    const graph = buildDependencyGraph({
      dt_node_path: imrView.dt_node_path,
      dependencies: [clockDependency, secondClock],
    });

    expect(
      graph.nodes.filter((node) => node.id === "dt:/soc/cpg@e6150000"),
    ).toHaveLength(1);
    expect(
      graph.edges.filter((edge) => edge.target === "dt:/soc/cpg@e6150000"),
    ).toHaveLength(2);
  });

  it("renders ambiguous runtime IRQs as multiple provider children", () => {
    const graph = buildDependencyGraph({
      dt_node_path: imrView.dt_node_path,
      dependencies: [
        {
          ...interruptDependency,
          interrupt_resolution: "ambiguous",
          runtime_interrupt: null,
          runtime_candidates: [
            runtimeIrq214,
            {
              ...runtimeIrq214,
              irq: 215,
              actions: ["imr-alt"],
            },
          ],
        },
      ],
    });

    expect(graph.nodes.map((node) => node.id)).toEqual(
      expect.arrayContaining(["irq:214", "irq:215"]),
    );
    expect(
      graph.edges.filter((edge) => edge.resolution === "ambiguous"),
    ).toHaveLength(2);
  });

  it("preserves static dependency edge when runtime IRQ is unavailable", () => {
    const graph = buildDependencyGraph({
      dt_node_path: imrView.dt_node_path,
      dependencies: [
        {
          ...interruptDependency,
          interrupt_resolution: "unavailable",
          runtime_interrupt: null,
          runtime_candidates: [],
        },
      ],
    });

    expect(
      graph.edges.some(
        (edge) =>
          edge.relation === "static_dependency" &&
          edge.target === "dt:/soc/interrupt-controller@f1000000",
      ),
    ).toBe(true);
    expect(graph.nodes.some((node) => node.label === "Runtime unavailable")).toBe(
      true,
    );
    expect(
      graph.edges.some(
        (edge) =>
          edge.relation === "runtime_mapping" &&
          edge.resolution === "unavailable",
      ),
    ).toBe(true);
  });

  it("marks provider nodes selectable only when a dependency view exists", () => {
    const graph = buildDependencyGraph(imrView, [
      imrView,
      {
        dt_node_path: "/soc/cpg@e6150000",
        dependencies: [],
      },
    ]);

    expect(
      graph.nodes.find((node) => node.id === "dt:/soc/cpg@e6150000")
        ?.selectable,
    ).toBe(true);
    expect(
      graph.nodes.find((node) => node.id === "dt:/soc/ipmmu@e6740000")
        ?.selectable,
    ).toBe(false);
  });
});
