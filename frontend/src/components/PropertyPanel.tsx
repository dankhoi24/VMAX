import type {
  DeviceTreeNode,
  DeviceTreeProperty,
  PropertyValue,
} from "../models/devicetree";

interface PropertyPanelProps {
  node: DeviceTreeNode | null;
}

export function PropertyPanel({ node }: PropertyPanelProps) {
  if (!node) {
    return (
      <aside className="property-panel" aria-label="Node properties">
        <div className="property-panel-empty">Select a node to inspect.</div>
      </aside>
    );
  }

  return (
    <aside className="property-panel" aria-label="Node properties">
      <div className="property-panel-header">
        <h2>Node</h2>
        <span>{node.properties.length.toLocaleString()} properties</span>
      </div>

      <dl className="node-metadata">
        <MetadataField label="full_name" value={node.full_name} />
        <MetadataField label="path" value={node.path} />
        <MetadataField label="unit_address" value={node.unit_address} />
        <MetadataField label="parent_path" value={node.parent_path} />
      </dl>

      <section className="properties-section" aria-labelledby="properties-heading">
        <h3 id="properties-heading">Properties</h3>
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
}

function MetadataField({ label, value }: MetadataFieldProps) {
  return (
    <div className="metadata-row">
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "null"}</code>
      </dd>
    </div>
  );
}

interface PropertyItemProps {
  property: DeviceTreeProperty;
}

function PropertyItem({ property }: PropertyItemProps) {
  return (
    <li className="property-item">
      <div className="property-item-header">
        <span className="property-name">{property.name}</span>
        <span className="property-kind">{property.kind}</span>
      </div>
      <dl className="property-fields">
        <div>
          <dt>value</dt>
          <dd>
            <code>{formatPropertyValue(property.value)}</code>
          </dd>
        </div>
        <div>
          <dt>raw_hex</dt>
          <dd>
            <code>{property.raw_hex || "(empty)"}</code>
          </dd>
        </div>
      </dl>
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
