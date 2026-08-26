import type {
  DependencyGraph,
  DependencyGraphEdge,
  DependencyGraphNode,
} from "../models/dependencyGraph";
import type {
  DependencyKind,
  DependencyResolution,
  DependencyRuntimeInterrupt,
  DeviceDependency,
  DeviceDependencyView,
} from "../models/dependency";

export function buildDependencyGraph(
  focus: DeviceDependencyView,
  allViews: DeviceDependencyView[] = [focus],
): DependencyGraph {
  const selectablePaths = new Set(allViews.map((view) => view.dt_node_path));
  const nodes = new Map<string, DependencyGraphNode>();
  const edges: DependencyGraphEdge[] = [];
  const providerRows = new Map<string, number>();
  const runtimeRows = new Map<string, number>();

  const focusNodeId = dtNodeId(focus.dt_node_path);
  nodes.set(focusNodeId, {
    id: focusNodeId,
    type: "device",
    lane: "consumer",
    row: 0,
    label: formatDtLabel(focus.dt_node_path),
    subtitle: focus.dt_node_path,
    dtPath: focus.dt_node_path,
    runtimeIrq: null,
    resolution: null,
    selectable: selectablePaths.has(focus.dt_node_path),
  });

  focus.dependencies.forEach((dependency) => {
    const providerId = getProviderNodeId(dependency);
    const providerRow = getOrAssignRow(providerRows, providerId);

    if (!nodes.has(providerId)) {
      nodes.set(providerId, buildProviderNode(dependency, providerId, providerRow, selectablePaths));
    }

    edges.push({
      id: [
        "static",
        dependency.kind,
        dependency.consumer_dt_path,
        dependency.entry_index,
        providerId,
      ].join(":"),
      source: focusNodeId,
      target: providerId,
      kind: dependency.kind,
      relation: "static_dependency",
      resolution: dependency.static_resolution,
      label: formatKind(dependency.kind),
    });

    if (dependency.kind === "interrupt") {
      appendRuntimeInterruptNodes(
        dependency,
        providerId,
        providerRow,
        nodes,
        edges,
        runtimeRows,
      );
    }
  });

  return {
    focusNodeId,
    nodes: normalizeRows(Array.from(nodes.values())),
    edges,
  };
}

function buildProviderNode(
  dependency: DeviceDependency,
  id: string,
  row: number,
  selectablePaths: Set<string>,
): DependencyGraphNode {
  if (dependency.provider_dt_path !== null) {
    return {
      id,
      type: "provider",
      lane: "provider",
      row,
      label: formatDtLabel(dependency.provider_dt_path),
      subtitle: dependency.provider_dt_path,
      dtPath: dependency.provider_dt_path,
      runtimeIrq: null,
      resolution: dependency.static_resolution,
      selectable: selectablePaths.has(dependency.provider_dt_path),
    };
  }

  return {
    id,
    type: "provider",
    lane: "provider",
    row,
    label: `Provider ${formatResolution(dependency.static_resolution)}`,
    subtitle: dependency.source_property ?? formatKind(dependency.kind),
    dtPath: null,
    runtimeIrq: null,
    resolution: dependency.static_resolution,
    selectable: false,
  };
}

function appendRuntimeInterruptNodes(
  dependency: DeviceDependency,
  providerId: string,
  providerRow: number,
  nodes: Map<string, DependencyGraphNode>,
  edges: DependencyGraphEdge[],
  runtimeRows: Map<string, number>,
): void {
  if (dependency.interrupt_resolution === "resolved" && dependency.runtime_interrupt) {
    appendRuntimeInterruptNode(
      dependency,
      dependency.runtime_interrupt,
      providerId,
      providerRow,
      "resolved",
      nodes,
      edges,
      runtimeRows,
    );
    return;
  }

  if (
    dependency.interrupt_resolution === "ambiguous" &&
    dependency.runtime_candidates.length > 0
  ) {
    dependency.runtime_candidates.forEach((candidate) => {
      appendRuntimeInterruptNode(
        dependency,
        candidate,
        providerId,
        providerRow,
        "ambiguous",
        nodes,
        edges,
        runtimeRows,
      );
    });
    return;
  }

  const resolution = dependency.interrupt_resolution ?? "unavailable";
  const statusId = [
    "runtime",
    resolution,
    dependency.consumer_dt_path,
    dependency.entry_index,
    providerId,
  ].join(":");
  const row = getOrAssignRuntimeRow(runtimeRows, statusId, providerRow);

  nodes.set(statusId, {
    id: statusId,
    type: "runtime_irq",
    lane: "runtime",
    row,
    label: `Runtime ${formatResolution(resolution)}`,
    subtitle: dependency.interrupt_match_method ?? null,
    dtPath: null,
    runtimeIrq: null,
    resolution,
    selectable: false,
  });
  edges.push(runtimeEdge(dependency, providerId, statusId, resolution, "runtime"));
}

function appendRuntimeInterruptNode(
  dependency: DeviceDependency,
  interrupt: DependencyRuntimeInterrupt,
  providerId: string,
  providerRow: number,
  resolution: DependencyResolution,
  nodes: Map<string, DependencyGraphNode>,
  edges: DependencyGraphEdge[],
  runtimeRows: Map<string, number>,
): void {
  const id = runtimeIrqNodeId(interrupt.irq);
  const row = getOrAssignRuntimeRow(runtimeRows, id, providerRow);

  if (!nodes.has(id)) {
    nodes.set(id, {
      id,
      type: "runtime_irq",
      lane: "runtime",
      row,
      label: `Linux IRQ${interrupt.irq}`,
      subtitle: formatRuntimeInterruptSubtitle(interrupt),
      dtPath: null,
      runtimeIrq: interrupt.irq,
      resolution,
      selectable: false,
    });
  }

  edges.push(
    runtimeEdge(
      dependency,
      providerId,
      id,
      resolution,
      formatRuntimeEdgeLabel(interrupt),
    ),
  );
}

function runtimeEdge(
  dependency: DeviceDependency,
  source: string,
  target: string,
  resolution: DependencyResolution,
  label: string,
): DependencyGraphEdge {
  return {
    id: [
      "runtime",
      dependency.consumer_dt_path,
      dependency.entry_index,
      target,
    ].join(":"),
    source,
    target,
    kind: "interrupt",
    relation: "runtime_mapping",
    resolution,
    label,
  };
}

function normalizeRows(nodes: DependencyGraphNode[]): DependencyGraphNode[] {
  const laneCounts = new Map<string, number>();
  for (const node of nodes) {
    laneCounts.set(node.lane, Math.max(laneCounts.get(node.lane) ?? 0, node.row + 1));
  }

  const maxRows = Math.max(...laneCounts.values(), 1);
  return nodes
    .map((node) =>
      node.lane === "consumer"
        ? { ...node, row: Math.max(0, Math.floor((maxRows - 1) / 2)) }
        : node,
    )
    .sort((a, b) => a.row - b.row || laneOrder(a.lane) - laneOrder(b.lane) || a.label.localeCompare(b.label));
}

function getProviderNodeId(dependency: DeviceDependency): string {
  if (dependency.provider_dt_path !== null) {
    return dtNodeId(dependency.provider_dt_path);
  }

  return [
    "provider",
    dependency.kind,
    dependency.consumer_dt_path,
    dependency.entry_index,
    dependency.static_resolution,
  ].join(":");
}

function dtNodeId(path: string): string {
  return `dt:${path}`;
}

function runtimeIrqNodeId(irq: number): string {
  return `irq:${irq}`;
}

function getOrAssignRow(rows: Map<string, number>, id: string): number {
  const existing = rows.get(id);
  if (existing !== undefined) {
    return existing;
  }

  const row = rows.size;
  rows.set(id, row);
  return row;
}

function getOrAssignRuntimeRow(
  rows: Map<string, number>,
  id: string,
  preferredRow: number,
): number {
  const existing = rows.get(id);
  if (existing !== undefined) {
    return existing;
  }

  const usedRows = new Set(rows.values());
  let row = preferredRow;
  while (usedRows.has(row)) {
    row += 1;
  }

  rows.set(id, row);
  return row;
}

function formatDtLabel(path: string): string {
  if (path === "/") {
    return "/";
  }

  return path.split("/").filter(Boolean).at(-1) ?? path;
}

function formatKind(kind: DependencyKind): string {
  return kind.replaceAll("_", " ").toUpperCase();
}

function formatResolution(resolution: DependencyResolution): string {
  return resolution.replaceAll("_", " ");
}

function formatRuntimeInterruptSubtitle(
  interrupt: DependencyRuntimeInterrupt,
): string {
  const pieces = [
    interrupt.controller,
    interrupt.hardware_irq === null ? null : `HWIRQ ${interrupt.hardware_irq}`,
    `${interrupt.total_count.toLocaleString()} count`,
  ].filter((value): value is string => Boolean(value));

  return pieces.join(" / ");
}

function formatRuntimeEdgeLabel(interrupt: DependencyRuntimeInterrupt): string {
  return interrupt.hardware_irq === null
    ? `IRQ ${interrupt.irq}`
    : `HWIRQ ${interrupt.hardware_irq}`;
}

function laneOrder(lane: string): number {
  if (lane === "consumer") {
    return 0;
  }

  if (lane === "provider") {
    return 1;
  }

  return 2;
}
