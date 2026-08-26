import type { DependencyKind, DependencyResolution } from "./dependency";

export type DependencyGraphNodeType = "device" | "provider" | "runtime_irq";
export type DependencyGraphLane = "consumer" | "provider" | "runtime";
export type DependencyGraphEdgeRelation = "static_dependency" | "runtime_mapping";

export interface DependencyGraphNode {
  id: string;
  type: DependencyGraphNodeType;
  lane: DependencyGraphLane;
  row: number;
  label: string;
  subtitle: string | null;
  dtPath: string | null;
  runtimeIrq: number | null;
  resolution: DependencyResolution | null;
  selectable: boolean;
}

export interface DependencyGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: DependencyKind;
  relation: DependencyGraphEdgeRelation;
  resolution: DependencyResolution;
  label: string;
}

export interface DependencyGraph {
  focusNodeId: string;
  nodes: DependencyGraphNode[];
  edges: DependencyGraphEdge[];
}
