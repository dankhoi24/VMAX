import { useEffect, useState } from "react";

import type { DeviceTreeNode } from "../models/devicetree";

interface DeviceTreeViewProps {
  root: DeviceTreeNode;
  nodeCount: number;
  selectedPath: string | null;
  onSelectNode: (node: DeviceTreeNode) => void;
}

export function DeviceTreeView({
  root,
  nodeCount,
  selectedPath,
  onSelectNode,
}: DeviceTreeViewProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(
    () => new Set([root.path]),
  );

  useEffect(() => {
    setExpandedPaths(new Set([root.path]));
  }, [root]);

  const toggleNode = (path: string) => {
    setExpandedPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  return (
    <section className="tree-surface" aria-label="Device Tree">
      <div className="tree-toolbar">
        <h2>Device Tree</h2>
        <span>{nodeCount.toLocaleString()} nodes</span>
      </div>
      <div className="tree-scroll">
        <ul className="tree-list" role="tree">
          <DeviceTreeNodeView
            node={root}
            depth={0}
            expandedPaths={expandedPaths}
            selectedPath={selectedPath}
            onToggle={toggleNode}
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
  onToggle: (path: string) => void;
  onSelectNode: (node: DeviceTreeNode) => void;
}

function DeviceTreeNodeView({
  node,
  depth,
  expandedPaths,
  selectedPath,
  onToggle,
  onSelectNode,
}: DeviceTreeNodeViewProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;

  return (
    <li
      className="tree-item"
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
    >
      <div
        className={isSelected ? "tree-row tree-row-selected" : "tree-row"}
        style={{ paddingLeft: 12 + depth * 20 }}
      >
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
              onToggle={onToggle}
              onSelectNode={onSelectNode}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
