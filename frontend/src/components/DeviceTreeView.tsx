import { useEffect, useMemo, useState } from "react";

import type { DeviceTreeNode } from "../models/devicetree";

interface DeviceTreeViewProps {
  root: DeviceTreeNode;
  nodeCount: number;
}

export function DeviceTreeView({ root, nodeCount }: DeviceTreeViewProps) {
  const allPaths = useMemo(() => collectPaths(root), [root]);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(
    () => new Set(allPaths),
  );

  useEffect(() => {
    setExpandedPaths(new Set(allPaths));
  }, [allPaths]);

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
            onToggle={toggleNode}
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
  onToggle: (path: string) => void;
}

function DeviceTreeNodeView({
  node,
  depth,
  expandedPaths,
  onToggle,
}: DeviceTreeNodeViewProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);

  return (
    <li
      className="tree-item"
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
    >
      <div
        className="tree-row"
        style={{ paddingLeft: 12 + depth * 20 }}
      >
        {hasChildren ? (
          <button
            className="tree-toggle"
            type="button"
            onClick={() => onToggle(node.path)}
            title="Toggle node"
            aria-label={`Toggle ${node.full_name}`}
          >
            {isExpanded ? "▾" : "▸"}
          </button>
        ) : (
          <span className="tree-toggle tree-toggle-placeholder" aria-hidden="true" />
        )}
        <span className="tree-node-name">{node.full_name}</span>
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
              onToggle={onToggle}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function collectPaths(root: DeviceTreeNode): string[] {
  const paths: string[] = [];
  const visit = (node: DeviceTreeNode) => {
    paths.push(node.path);
    node.children.forEach(visit);
  };

  visit(root);
  return paths;
}
