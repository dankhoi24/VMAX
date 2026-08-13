import type { MemoryRegion } from "../models/addressing";

type RegionRelation = "normal" | "nested" | "overlap";

interface NormalizedRegion {
  order: number;
  region: MemoryRegion;
  start: bigint;
  end: bigint | null;
  size: bigint | null;
}

export type AddressSpaceEntry =
  | {
      entryKind: "gap";
      start: bigint;
      end: bigint;
      size: bigint;
    }
  | {
      entryKind: "region";
      region: MemoryRegion;
      start: bigint;
      end: bigint | null;
      size: bigint | null;
      relation: RegionRelation;
    };

interface AddressSpaceMapProps {
  regions: MemoryRegion[];
  selectedNodePath?: string | null;
  onSelectRegion?: (nodePath: string) => void;
}

const REGION_LABELS: Record<MemoryRegion["kind"], string> = {
  device: "DEVICE",
  ram: "RAM",
  reserved: "RESERVED",
};

export function AddressSpaceMap({
  regions,
  selectedNodePath = null,
  onSelectRegion,
}: AddressSpaceMapProps) {
  const entries = buildAddressSpaceEntries(regions);
  const gapCount = entries.filter((entry) => entry.entryKind === "gap").length;
  const regionCount = entries.length - gapCount;

  if (entries.length === 0) {
    return (
      <p className="addressing-empty-text">
        No CPU physical address regions described.
      </p>
    );
  }

  return (
    <div className="address-space-map" aria-label="CPU Physical Address Space">
      <div className="address-space-summary" aria-label="Address space summary">
        <span>{regionCount.toLocaleString()} regions</span>
        {gapCount > 0 && <span>{gapCount.toLocaleString()} gaps</span>}
      </div>
      <ol className="address-space-list">
        {renderAddressSpaceEntries(entries, selectedNodePath, onSelectRegion)}
      </ol>
    </div>
  );
}

export function buildAddressSpaceEntries(
  regions: MemoryRegion[],
): AddressSpaceEntry[] {
  const normalized = regions
    .map(normalizeRegion)
    .filter((region): region is NormalizedRegion => region !== null)
    .sort(compareNormalizedRegions);
  const entries: AddressSpaceEntry[] = [];
  let coverageEnd: bigint | null = null;

  for (const item of normalized) {
    let relation: RegionRelation = "normal";

    if (coverageEnd === null) {
      if (item.start > 0n) {
        entries.push({
          entryKind: "gap",
          start: 0n,
          end: item.start - 1n,
          size: item.start,
        });
      }
    } else if (item.start > coverageEnd + 1n) {
      entries.push({
        entryKind: "gap",
        start: coverageEnd + 1n,
        end: item.start - 1n,
        size: item.start - coverageEnd - 1n,
      });
    } else if (item.start <= coverageEnd) {
      relation =
        item.end !== null && item.end <= coverageEnd ? "nested" : "overlap";
    }

    entries.push({
      entryKind: "region",
      region: item.region,
      start: item.start,
      end: item.end,
      size: item.size,
      relation,
    });

    if (item.end !== null && (coverageEnd === null || item.end > coverageEnd)) {
      coverageEnd = item.end;
    }
  }

  return entries;
}

function renderAddressSpaceEntries(
  entries: AddressSpaceEntry[],
  selectedNodePath: string | null,
  onSelectRegion: ((nodePath: string) => void) | undefined,
) {
  let regionOrdinal = 0;

  return entries.map((entry, index) => {
    if (entry.entryKind === "gap") {
      return (
        <AddressSpaceGap
          entry={entry}
          key={`gap:${entry.start.toString()}:${entry.end.toString()}`}
        />
      );
    }

    regionOrdinal += 1;

    return (
      <AddressSpaceRegion
        entry={entry}
        ordinal={regionOrdinal}
        isSelected={entry.region.node_path === selectedNodePath}
        key={`${entry.region.node_path}:${entry.region.start}:${index}`}
        onSelectRegion={onSelectRegion}
      />
    );
  });
}

interface AddressSpaceGapProps {
  entry: Extract<AddressSpaceEntry, { entryKind: "gap" }>;
}

function AddressSpaceGap({ entry }: AddressSpaceGapProps) {
  return (
    <li className="address-space-entry address-space-gap">
      <div className="address-space-entry-marker" aria-hidden="true">
        <span>gap</span>
      </div>
      <div className="address-space-gap-body">
        <span>gap</span>
        <AddressSpaceFields
          fields={[
            ["Start", formatHex(entry.start)],
            ["End", formatHex(entry.end)],
            ["Size", formatHex(entry.size)],
          ]}
        />
      </div>
    </li>
  );
}

interface AddressSpaceRegionProps {
  entry: Extract<AddressSpaceEntry, { entryKind: "region" }>;
  ordinal: number;
  isSelected: boolean;
  onSelectRegion?: (nodePath: string) => void;
}

function AddressSpaceRegion({
  entry,
  ordinal,
  isSelected,
  onSelectRegion,
}: AddressSpaceRegionProps) {
  const content = (
    <>
      <div className="address-space-region-main">
        <span
          className={`address-space-kind address-space-kind-${entry.region.kind}`}
        >
          {REGION_LABELS[entry.region.kind]}
        </span>
        <code>{entry.region.node_path}</code>
        {entry.relation !== "normal" && (
          <span
            className={`address-space-relation address-space-relation-${entry.relation}`}
          >
            {entry.relation}
          </span>
        )}
        {isSelected && <span className="address-space-selected">selected</span>}
      </div>
      <AddressSpaceFields
        fields={[
          ["Start", entry.region.start],
          ["End", entry.region.end],
          ["Size", entry.region.size],
        ]}
      />
    </>
  );
  const controlClassName = isSelected
    ? "address-space-region-control address-space-region-control-selected"
    : "address-space-region-control";

  return (
    <li
      className={`address-space-entry address-space-region address-space-region-${entry.region.kind} address-space-region-${entry.relation}`}
    >
      <div className="address-space-entry-marker" aria-hidden="true">
        <span>{ordinal}</span>
      </div>
      {onSelectRegion ? (
        <button
          className={controlClassName}
          type="button"
          onClick={() => onSelectRegion(entry.region.node_path)}
          aria-label={`Select address region ${entry.region.node_path}`}
        >
          {content}
        </button>
      ) : (
        <div className={controlClassName}>{content}</div>
      )}
    </li>
  );
}

interface AddressSpaceFieldsProps {
  fields: Array<[label: string, value: string | null]>;
}

function AddressSpaceFields({ fields }: AddressSpaceFieldsProps) {
  return (
    <dl className="address-space-fields">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <code>{value ?? "-"}</code>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function normalizeRegion(region: MemoryRegion, order: number): NormalizedRegion | null {
  const start = parseAddress(region.start);

  if (start === null) {
    return null;
  }

  return {
    order,
    region,
    start,
    end: parseAddress(region.end),
    size: parseAddress(region.size),
  };
}

function compareNormalizedRegions(
  left: NormalizedRegion,
  right: NormalizedRegion,
): number {
  if (left.start < right.start) {
    return -1;
  }
  if (left.start > right.start) {
    return 1;
  }
  if (left.end !== null && right.end !== null && left.end !== right.end) {
    return left.end > right.end ? -1 : 1;
  }
  if (left.end !== null && right.end === null) {
    return -1;
  }
  if (left.end === null && right.end !== null) {
    return 1;
  }

  return left.order - right.order;
}

function parseAddress(value: string | null): bigint | null {
  if (value === null) {
    return null;
  }

  try {
    return BigInt(value);
  } catch {
    return null;
  }
}

function formatHex(value: bigint): string {
  return `0x${value.toString(16)}`;
}
