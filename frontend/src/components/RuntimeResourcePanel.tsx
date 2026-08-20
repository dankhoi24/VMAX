import type { RuntimeResource } from "../models/runtime";
import { formatHex } from "../models/runtime";

interface RuntimeResourcePanelProps {
  resources: RuntimeResource[];
}

export function RuntimeResourcePanel({ resources }: RuntimeResourcePanelProps) {
  return (
    <section
      className="runtime-resource-panel"
      aria-labelledby="runtime-resources-heading"
    >
      <div className="runtime-resource-heading">
        <h3 id="runtime-resources-heading">Runtime Resources</h3>
        <span className="runtime-resource-count">
          {resources.length.toLocaleString()}
        </span>
      </div>

      {resources.length === 0 ? (
        <p className="runtime-resource-empty">
          No runtime resources exposed for this device.
        </p>
      ) : (
        <ul className="runtime-resource-list">
          {resources.map((resource) => (
            <RuntimeResourceItem key={resource.index} resource={resource} />
          ))}
        </ul>
      )}
    </section>
  );
}

interface RuntimeResourceItemProps {
  resource: RuntimeResource;
}

function RuntimeResourceItem({ resource }: RuntimeResourceItemProps) {
  return (
    <li className="runtime-resource-item">
      <div className="runtime-resource-item-header">
        <strong>Resource #{resource.index}</strong>
        <FlagList flagNames={resource.flag_names} />
      </div>
      <dl className="runtime-resource-grid">
        <RuntimeResourceField
          label="Type"
          value={formatFlagNames(resource.flag_names)}
        />
        <RuntimeResourceField label="Name" value={resource.name} />
        <RuntimeResourceField label="Start" value={formatHex(resource.start)} />
        <RuntimeResourceField label="End" value={formatHex(resource.end)} />
        <RuntimeResourceField label="Size" value={formatHex(resource.size)} />
        <RuntimeResourceField label="Flags" value={formatHex(resource.flags)} />
      </dl>
    </li>
  );
}

interface FlagListProps {
  flagNames: string[];
}

function FlagList({ flagNames }: FlagListProps) {
  if (flagNames.length === 0) {
    return <span className="runtime-resource-flag">raw</span>;
  }

  return (
    <span className="runtime-resource-flags" aria-label="Decoded flags">
      {flagNames.map((flagName) => (
        <span className="runtime-resource-flag" key={flagName}>
          {flagName}
        </span>
      ))}
    </span>
  );
}

interface RuntimeResourceFieldProps {
  label: string;
  value: string | null;
}

function RuntimeResourceField({ label, value }: RuntimeResourceFieldProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "-"}</code>
      </dd>
    </div>
  );
}

function formatFlagNames(flagNames: string[]): string {
  if (flagNames.length === 0) {
    return "-";
  }

  return flagNames.join(" | ");
}
