import type { DependencyKind, DeviceDependency } from "../models/dependency";
import { DependencyRow } from "./DependencyRow";

interface DependencySectionProps {
  kind: DependencyKind;
  dependencies: DeviceDependency[];
}

export function DependencySection({
  kind,
  dependencies,
}: DependencySectionProps) {
  if (dependencies.length === 0) {
    return null;
  }

  return (
    <section className="dependency-section">
      <div className="dependency-section-heading">
        <h4>{formatKind(kind)}</h4>
        <span>{dependencies.length.toLocaleString()}</span>
      </div>
      <ul className="dependency-row-list">
        {dependencies.map((dependency) => (
          <li key={getDependencyKey(dependency)}>
            <DependencyRow dependency={dependency} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function getDependencyKey(dependency: DeviceDependency): string {
  return [
    dependency.kind,
    dependency.consumer_dt_path,
    dependency.source_property,
    dependency.entry_index,
    dependency.provider_dt_path,
    dependency.provider_phandle,
  ].join(":");
}

function formatKind(kind: string): string {
  return kind.replaceAll("_", " ").toUpperCase();
}
