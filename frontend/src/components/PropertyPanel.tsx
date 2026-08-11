import { useEffect, useState } from "react";

import type {
  DeviceTreeNode,
  DeviceTreeProperty,
  PropertyValue,
} from "../models/devicetree";
import { CheckIcon, CopyIcon, NodeIcon, PropertiesIcon } from "./icons";

interface PropertyPanelProps {
  node: DeviceTreeNode | null;
}

export function PropertyPanel({ node }: PropertyPanelProps) {
  if (!node) {
    return (
      <aside className="property-panel" aria-label="Node properties">
        <div className="property-panel-empty">
          <NodeIcon className="empty-icon" />
          <span>Select a node to inspect.</span>
        </div>
      </aside>
    );
  }

  return (
    <aside className="property-panel" aria-label="Node properties">
      <div className="property-panel-header">
        <div className="panel-title">
          <NodeIcon className="panel-icon" />
          <h2>Node</h2>
        </div>
      </div>

      <dl className="node-metadata">
        <MetadataField
          label="Full Name"
          value={node.full_name}
          copyValue={node.full_name}
        />
        <MetadataField label="Path" value={node.path} copyValue={node.path} />
        <MetadataField label="Unit Address" value={node.unit_address} />
        <MetadataField
          label="Parent Path"
          value={node.parent_path}
          copyValue={node.parent_path}
        />
      </dl>

      <section className="properties-section" aria-labelledby="properties-heading">
        <div className="properties-heading-row">
          <div className="panel-title">
            <PropertiesIcon className="panel-icon" />
            <h3 id="properties-heading">Properties</h3>
          </div>
          <span className="property-count-badge">
            {node.properties.length.toLocaleString()}
          </span>
        </div>
        {node.properties.length === 0 ? (
          <p className="property-empty">No properties</p>
        ) : (
          <ul className="property-list">
            {node.properties.map((property) => (
              <PropertyItem key={property.name} property={property} />
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

interface MetadataFieldProps {
  label: string;
  value: string | null;
  copyValue?: string | null;
}

function MetadataField({ label, value, copyValue }: MetadataFieldProps) {
  const displayValue = value ?? "-";

  return (
    <div className="metadata-row">
      <dt>{label}</dt>
      <dd>
        <code>{displayValue}</code>
        {copyValue && <CopyButton value={copyValue} label={label} />}
      </dd>
    </div>
  );
}

interface PropertyItemProps {
  property: DeviceTreeProperty;
}

function PropertyItem({ property }: PropertyItemProps) {
  const formattedValue = formatPropertyValue(property.value);
  const rawValue = property.raw_hex || "(empty)";

  return (
    <li className="property-item">
      <div className="property-item-header">
        <span className="property-name">{property.name}</span>
        <span className={getPropertyKindClassName(property.kind)}>
          {property.kind}
        </span>
      </div>
      <dl className="property-fields">
        <div>
          <dt>value</dt>
          <dd>
            <code>{formattedValue}</code>
            <CopyButton
              value={formattedValue}
              label={`${property.name} value`}
            />
          </dd>
        </div>
      </dl>
      <details className="raw-detail">
        <summary>Raw (hex)</summary>
        <div className="raw-detail-content">
          <code>{rawValue}</code>
          <CopyButton
            value={property.raw_hex}
            label={`${property.name} raw hex`}
          />
        </div>
      </details>
    </li>
  );
}

function formatPropertyValue(value: PropertyValue): string {
  if (value === null) {
    return "null";
  }

  if (typeof value === "string" || Array.isArray(value)) {
    return JSON.stringify(value) ?? "null";
  }

  return String(value);
}

interface CopyButtonProps {
  label: string;
  value: string;
}

function CopyButton({ label, value }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) {
      return;
    }

    const timeoutId = window.setTimeout(() => setCopied(false), 3000);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  const handleCopy = async () => {
    if (await copyToClipboard(value)) {
      setCopied(true);
    }
  };

  return (
    <button
      className={copied ? "copy-button copy-button-copied" : "copy-button"}
      type="button"
      onClick={handleCopy}
      aria-label={copied ? `Copied ${label}` : `Copy ${label}`}
      title={copied ? "Copied" : `Copy ${label}`}
    >
      {copied ? (
        <CheckIcon className="copy-icon" />
      ) : (
        <CopyIcon className="copy-icon" />
      )}
    </button>
  );
}

async function copyToClipboard(value: string): Promise<boolean> {
  if (!navigator.clipboard) {
    return false;
  }

  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function getPropertyKindClassName(kind: DeviceTreeProperty["kind"]): string {
  return `property-kind property-kind-${kind.replace("_", "-")}`;
}
