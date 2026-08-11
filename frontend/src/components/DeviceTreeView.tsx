import { useEffect, useRef } from "react";

import type { DeviceTreeNode } from "../models/devicetree";
import { NodeIcon, TreeIcon } from "./icons";

interface DeviceTreeViewProps {
  root: DeviceTreeNode;
  nodeCount: number;
  expandedPaths: Set<string>;
  selectedPath: string | null;
  selectionRequest: number;
  onToggleNode: (path: string) => void;
  onSelectNode: (node: DeviceTreeNode) => void;
}

export function DeviceTreeView({
  root,
  nodeCount,
  expandedPaths,
  selectedPath,
  selectionRequest,
  onToggleNode,
  onSelectNode,
}: DeviceTreeViewProps) {
  return (
    <section className="tree-surface" aria-label="Device Tree">
      <div className="tree-toolbar">
        <div className="panel-title">
          <TreeIcon className="panel-icon" />
          <h2>Device Tree</h2>
        </div>
        <span>{nodeCount.toLocaleString()} nodes</span>
      </div>
      <div className="tree-scroll">
        <ul className="tree-list" role="tree">
          <DeviceTreeNodeView
            node={root}
            depth={0}
            expandedPaths={expandedPaths}
            selectedPath={selectedPath}
            selectionRequest={selectionRequest}
            onToggle={onToggleNode}
            onSelectNode={onSelectNode}
          />
        </ul>
      </div>
    </section>
  );
}

interface DeviceTreeNodeViewProps {
  node: DeviceTreeNode;
  depth: number;
  expandedPaths: Set<string>;
  selectedPath: string | null;
  selectionRequest: number;
  onToggle: (path: string) => void;
  onSelectNode: (node: DeviceTreeNode) => void;
}

function DeviceTreeNodeView({
  node,
  depth,
  expandedPaths,
  selectedPath,
  selectionRequest,
  onToggle,
  onSelectNode,
}: DeviceTreeNodeViewProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const rowRef = useRef<HTMLDivElement | null>(null);
  const guides = Array.from({ length: depth }, (_, index) => index);

  useEffect(() => {
    if (isSelected) {
      rowRef.current?.scrollIntoView?.({
        block: "nearest",
        inline: "nearest",
      });
    }
  }, [isSelected, selectionRequest]);

  return (
    <li
      className="tree-item"
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
    >
      <div
        className={isSelected ? "tree-row tree-row-selected" : "tree-row"}
        ref={rowRef}
        style={{ paddingLeft: 12 + depth * 20 }}
      >
        {guides.map((index) => (
          <span
            className="tree-guide"
            key={index}
            style={{ left: 24 + index * 20 }}
          />
        ))}
        {hasChildren ? (
          <button
            className="tree-toggle"
            type="button"
            onClick={() => onToggle(node.path)}
            title="Expand or collapse node"
            aria-label={`Toggle ${node.full_name}`}
          >
            {isExpanded ? "▾" : "▸"}
          </button>
        ) : (
          <span className="tree-toggle tree-toggle-placeholder" aria-hidden="true" />
        )}
        <button
          className="tree-node-button"
          type="button"
          onClick={() => onSelectNode(node)}
          aria-current={isSelected ? "true" : undefined}
        >
          <NodeIcon className="tree-node-icon" />
          <span className="tree-node-name">{node.full_name}</span>
        </button>
        {node.children.length > 0 && (
          <span className="tree-node-count">{node.children.length}</span>
        )}
      </div>
      {hasChildren && isExpanded && (
        <ul className="tree-list" role="group">
          {node.children.map((child) => (
            <DeviceTreeNodeView
              key={child.path}
              node={child}
              depth={depth + 1}
              expandedPaths={expandedPaths}
              selectedPath={selectedPath}
              selectionRequest={selectionRequest}
              onToggle={onToggle}
              onSelectNode={onSelectNode}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
