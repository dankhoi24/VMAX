import type {
  DependencyGraph as DependencyGraphModel,
  DependencyGraphEdge,
  DependencyGraphNode,
} from "../models/dependencyGraph";
import { AddressingIcon, NodeIcon, RuntimeIcon } from "./icons";

interface DependencyGraphProps {
  graph: DependencyGraphModel;
  onSelectDtPath?: (dtPath: string) => void;
}

const graphWidth = 860;
const nodeWidth = 180;
const nodeHeight = 64;
const rowGap = 96;
const topPadding = 20;
const laneX = {
  consumer: 28,
  provider: 330,
  runtime: 632,
} as const;

export function DependencyGraph({
  graph,
  onSelectDtPath,
}: DependencyGraphProps) {
  const nodePositions = new Map(
    graph.nodes.map((node) => [node.id, getNodePosition(node)]),
  );
  const maxRow = Math.max(...graph.nodes.map((node) => node.row), 0);
  const graphHeight = topPadding * 2 + nodeHeight + maxRow * rowGap;

  return (
    <section className="dependency-graph-panel" aria-label="Dependency graph">
      <div className="dependency-graph-heading">
        <h3>Focus Graph</h3>
        <span>{graph.edges.length.toLocaleString()} relations</span>
      </div>
      <p className="dependency-graph-caption">
        Dependency direction: consumer -&gt; provider -&gt; runtime
      </p>
      <div className="dependency-graph-scroll">
        <div
          className="dependency-graph-canvas"
          style={{ height: graphHeight, width: graphWidth }}
        >
          <svg
            className="dependency-graph-edges"
            aria-hidden="true"
            viewBox={`0 0 ${graphWidth} ${graphHeight}`}
          >
            <defs>
              <GraphArrowMarker resolution="resolved" />
              <GraphArrowMarker resolution="unresolved" />
              <GraphArrowMarker resolution="unavailable" />
              <GraphArrowMarker resolution="ambiguous" />
            </defs>
            {graph.edges.map((edge) => (
              <GraphEdge
                key={edge.id}
                edge={edge}
                nodes={graph.nodes}
                nodePositions={nodePositions}
              />
            ))}
          </svg>
          {graph.nodes.map((node) => (
            <GraphNode
              key={node.id}
              node={node}
              isFocus={node.id === graph.focusNodeId}
              onSelectDtPath={onSelectDtPath}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

interface GraphEdgeProps {
  edge: DependencyGraphEdge;
  nodes: DependencyGraphNode[];
  nodePositions: Map<string, GraphPosition>;
}

function GraphEdge({ edge, nodes, nodePositions }: GraphEdgeProps) {
  const source = nodes.find((node) => node.id === edge.source);
  const target = nodes.find((node) => node.id === edge.target);
  const sourcePosition = nodePositions.get(edge.source);
  const targetPosition = nodePositions.get(edge.target);

  if (!source || !target || !sourcePosition || !targetPosition) {
    return null;
  }

  const sourceX = sourcePosition.x + nodeWidth;
  const sourceY = sourcePosition.y + nodeHeight / 2;
  const targetX = targetPosition.x;
  const targetY = targetPosition.y + nodeHeight / 2;
  const midX = sourceX + (targetX - sourceX) / 2;
  const midY = sourceY + (targetY - sourceY) / 2;
  const curve = Math.max(56, Math.abs(targetX - sourceX) / 2);
  const path = `M ${sourceX} ${sourceY} C ${sourceX + curve} ${sourceY}, ${
    targetX - curve
  } ${targetY}, ${targetX} ${targetY}`;

  return (
    <g className={`dependency-graph-edge dependency-graph-edge-${edge.resolution}`}>
      <path d={path} markerEnd={`url(#dependency-arrow-${edge.resolution})`} />
      <text x={midX} y={midY - 7}>
        {edge.label}
      </text>
    </g>
  );
}

interface GraphArrowMarkerProps {
  resolution: DependencyGraphEdge["resolution"];
}

function GraphArrowMarker({ resolution }: GraphArrowMarkerProps) {
  return (
    <marker
      id={`dependency-arrow-${resolution}`}
      markerHeight="8"
      markerWidth="8"
      orient="auto"
      refX="7"
      refY="4"
      viewBox="0 0 8 8"
    >
      <path
        className={`dependency-graph-arrow dependency-graph-arrow-${resolution}`}
        d="M0 0 8 4 0 8Z"
      />
    </marker>
  );
}

interface GraphNodeProps {
  node: DependencyGraphNode;
  isFocus: boolean;
  onSelectDtPath?: (dtPath: string) => void;
}

function GraphNode({ node, isFocus, onSelectDtPath }: GraphNodeProps) {
  const position = getNodePosition(node);
  const content = (
    <>
      {getNodeIcon(node)}
      <span>
        <strong>{node.label}</strong>
        {node.subtitle && <small>{node.subtitle}</small>}
      </span>
    </>
  );
  const className = getNodeClassName(node, isFocus);
  const style = {
    height: nodeHeight,
    left: position.x,
    top: position.y,
    width: nodeWidth,
  };

  if (node.dtPath && node.selectable && onSelectDtPath) {
    return (
      <button
        aria-label={`Select dependency graph node ${node.label}`}
        className={className}
        style={style}
        type="button"
        onClick={() => onSelectDtPath(node.dtPath!)}
      >
        {content}
      </button>
    );
  }

  return (
    <div className={className} style={style}>
      {content}
    </div>
  );
}

interface GraphPosition {
  x: number;
  y: number;
}

function getNodePosition(node: DependencyGraphNode): GraphPosition {
  return {
    x: laneX[node.lane],
    y: topPadding + node.row * rowGap,
  };
}

function getNodeClassName(
  node: DependencyGraphNode,
  isFocus: boolean,
): string {
  return [
    "dependency-graph-node",
    `dependency-graph-node-${node.type}`,
    node.resolution ? `dependency-graph-node-${node.resolution}` : null,
    isFocus ? "dependency-graph-node-focus" : null,
    node.selectable ? "dependency-graph-node-selectable" : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join(" ");
}

function getNodeIcon(node: DependencyGraphNode) {
  if (node.type === "runtime_irq") {
    return <RuntimeIcon className="dependency-graph-node-icon" />;
  }

  if (node.type === "provider") {
    return <AddressingIcon className="dependency-graph-node-icon" />;
  }

  return <NodeIcon className="dependency-graph-node-icon" />;
}
