import type {
  DeviceTreeNode,
  DeviceTreeProperty,
  PropertyValue,
} from "../models/devicetree";

export type SearchMatchKind = "path" | "node" | "compatible" | "property";

export interface DeviceTreeSearchResult {
  node: DeviceTreeNode;
  matches: SearchMatchKind[];
}

export function searchDeviceTree(
  root: DeviceTreeNode,
  query: string,
): DeviceTreeSearchResult[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return [];
  }

  const results: DeviceTreeSearchResult[] = [];
  visit(root, (node) => {
    const matches = getNodeMatches(node, normalizedQuery);
    if (matches.length > 0) {
      results.push({ node, matches });
    }
  });

  return results;
}

export function getAncestorPaths(path: string): string[] {
  if (path === "/") {
    return ["/"];
  }

  const parts = path.split("/").filter(Boolean);
  const ancestors = ["/"];
  let currentPath = "";

  parts.slice(0, -1).forEach((part) => {
    currentPath += `/${part}`;
    ancestors.push(currentPath);
  });

  return ancestors;
}

function visit(node: DeviceTreeNode, callback: (node: DeviceTreeNode) => void) {
  callback(node);
  node.children.forEach((child) => visit(child, callback));
}

function getNodeMatches(
  node: DeviceTreeNode,
  normalizedQuery: string,
): SearchMatchKind[] {
  const matches: SearchMatchKind[] = [];

  if (includesQuery(node.path, normalizedQuery)) {
    matches.push("path");
  }

  if (
    includesQuery(node.name, normalizedQuery) ||
    includesQuery(node.full_name, normalizedQuery)
  ) {
    matches.push("node");
  }

  if (node.properties.some((property) => matchesCompatible(property, normalizedQuery))) {
    matches.push("compatible");
  }

  if (node.properties.some((property) => includesQuery(property.name, normalizedQuery))) {
    matches.push("property");
  }

  return matches;
}

function matchesCompatible(
  property: DeviceTreeProperty,
  normalizedQuery: string,
): boolean {
  return (
    property.name === "compatible" &&
    valueParts(property.value).some((part) => includesQuery(part, normalizedQuery))
  );
}

function valueParts(value: PropertyValue): string[] {
  if (value === null) {
    return [];
  }

  if (Array.isArray(value)) {
    return value.map(String);
  }

  return [String(value)];
}

function includesQuery(value: string, normalizedQuery: string): boolean {
  return value.toLowerCase().includes(normalizedQuery);
}
