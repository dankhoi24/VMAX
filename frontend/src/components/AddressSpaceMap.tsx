import { useEffect, useMemo, useState } from "react";

import type { MemoryRegion } from "../models/addressing";

type RegionRelation = "normal" | "nested" | "overlap";

interface NormalizedRegion {
  order: number;
  region: MemoryRegion;
  start: bigint;
  end: bigint;
  size: bigint | null;
}

interface AddressSpaceRange {
  start: bigint;
  end: bigint;
  span: bigint;
}

export interface AddressSpaceRegionEntry {
  entryKind: "region";
  region: MemoryRegion;
  start: bigint;
  end: bigint;
  size: bigint | null;
  relation: RegionRelation;
}

export interface AddressSpaceGapEntry {
  entryKind: "gap";
  start: bigint;
  end: bigint;
  size: bigint;
}

export type AddressSpaceEntry = AddressSpaceGapEntry | AddressSpaceRegionEntry;

interface AddressSpaceMapProps {
  regions: MemoryRegion[];
  selectedNodePath?: string | null;
  onSelectRegion?: (nodePath: string) => void;
}

const KIND_LANES: MemoryRegion["kind"][] = ["ram", "reserved", "device"];
const MAX_ZOOM = 4096;
const MIN_REGION_HEIGHT = 8;
const MIN_GAP_HEIGHT = 8;
const TARGET_SELECTED_HEIGHT = 64;
const VIEWPORT_HEIGHT = 520;

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
  const model = useMemo(() => buildAddressSpaceModel(regions), [regions]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState(0);
  const selectedRegion = model.regions.find(
    (entry) => entry.region.node_path === selectedNodePath,
  );
  const viewport = getViewportRange(model.range, zoom, pan);

  useEffect(() => {
    setZoom(1);
    setPan(0);
  }, [model.range.start, model.range.end]);

  useEffect(() => {
    if (selectedRegion) {
      focusRegion(selectedRegion);
    }
  }, [selectedNodePath, selectedRegion]);

  if (model.regions.length === 0) {
    return (
      <p className="addressing-empty-text">
        No CPU physical address regions described.
      </p>
    );
  }

  function fitAll() {
    setZoom(1);
    setPan(0);
  }

  function fitSelected() {
    if (selectedRegion) {
      focusRegion(selectedRegion);
    }
  }

  function focusRegion(region: AddressSpaceRegionEntry) {
    const nextZoom = getFitSelectedZoom(model.range, region);
    const nextViewport = getViewportRange(model.range, nextZoom, pan);
    const nextPan = getPanForCenter(
      model.range,
      nextZoom,
      getRegionCenter(region),
      nextViewport.span,
    );

    setZoom(nextZoom);
    setPan(nextPan);
  }

  function zoomBy(factor: number) {
    const center = viewport.start + viewport.span / 2n;
    const nextZoom = clampZoom(Math.round(zoom * factor));
    const nextViewport = getViewportRange(model.range, nextZoom, pan);
    setZoom(nextZoom);
    setPan(getPanForCenter(model.range, nextZoom, center, nextViewport.span));
  }

  function updatePan(nextPan: number) {
    setPan(clampPan(nextPan));
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? 0.5 : 2);
  }

  const visibleGaps = model.gaps.filter((gap) => intersects(gap, viewport));
  const visibleRegions = model.regions.filter((region) =>
    intersects(region, viewport),
  );
  const tickAddresses = getTickAddresses(viewport);

  return (
    <div className="address-space-map">
      <div className="address-space-toolbar" aria-label="Address space controls">
        <button type="button" onClick={() => zoomBy(0.5)}>
          -
        </button>
        <span>{formatZoom(zoom)}</span>
        <button type="button" onClick={() => zoomBy(2)}>
          +
        </button>
        <button type="button" onClick={fitAll}>
          Fit All
        </button>
        <button type="button" onClick={fitSelected} disabled={!selectedRegion}>
          Fit Selected
        </button>
      </div>

      <div className="address-space-window">
        <div className="address-space-readout" aria-label="Visible address range">
          <code>{formatHex(viewport.start)}</code>
          <span>-</span>
          <code>{formatHex(viewport.end)}</code>
        </div>

        <div
          className="address-space-viewport"
          aria-label="CPU Physical Address Space"
          onWheel={handleWheel}
        >
          <div className="address-space-axis" aria-hidden="true">
            {tickAddresses.map((address) => (
              <div
                className="address-space-tick"
                key={address.toString()}
                style={{
                  top: `${getAddressY(address, viewport)}px`,
                }}
              >
                <code>{formatHex(address)}</code>
              </div>
            ))}
          </div>

          <div className="address-space-lanes">
            {KIND_LANES.map((kind) => (
              <div className="address-space-lane" key={kind}>
                <div className="address-space-lane-heading">
                  {REGION_LABELS[kind]}
                </div>
              </div>
            ))}

            {visibleGaps.map((gap) => (
              <AddressSpaceGap
                gap={gap}
                key={`gap:${gap.start.toString()}:${gap.end.toString()}`}
                viewport={viewport}
              />
            ))}

            {visibleRegions.map((entry) => (
              <AddressSpaceRegion
                entry={entry}
                isSelected={entry.region.node_path === selectedNodePath}
                key={`${entry.region.node_path}:${entry.region.start}`}
                onSelectRegion={onSelectRegion}
                viewport={viewport}
              />
            ))}
          </div>
        </div>

        <label className="address-space-pan">
          <span>Pan</span>
          <input
            type="range"
            min="0"
            max="1000"
            value={pan}
            onChange={(event) => updatePan(Number(event.target.value))}
            disabled={zoom === 1}
            aria-label="Pan address space"
          />
        </label>
      </div>
    </div>
  );
}

export function buildAddressSpaceEntries(
  regions: MemoryRegion[],
): AddressSpaceEntry[] {
  return buildAddressSpaceModel(regions).entries;
}

function AddressSpaceGap({
  gap,
  viewport,
}: {
  gap: AddressSpaceGapEntry;
  viewport: AddressSpaceRange;
}) {
  const bounds = getVisibleBounds(gap.start, gap.end, viewport, MIN_GAP_HEIGHT);

  return (
    <div
      className="address-space-gap-band"
      style={{
        height: `${bounds.height}px`,
        top: `${bounds.top}px`,
      }}
    >
      <span>GAP</span>
      <code>
        {formatHex(gap.start)} - {formatHex(gap.end)}
      </code>
    </div>
  );
}

function AddressSpaceRegion({
  entry,
  isSelected,
  onSelectRegion,
  viewport,
}: {
  entry: AddressSpaceRegionEntry;
  isSelected: boolean;
  onSelectRegion?: (nodePath: string) => void;
  viewport: AddressSpaceRange;
}) {
  const bounds = getVisibleBounds(
    entry.start,
    entry.end,
    viewport,
    MIN_REGION_HEIGHT,
  );
  const laneIndex = KIND_LANES.indexOf(entry.region.kind);
  const className = [
    "address-space-block",
    `address-space-block-${entry.region.kind}`,
    `address-space-block-${entry.relation}`,
    isSelected ? "address-space-block-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const content = (
    <>
      <span>{REGION_LABELS[entry.region.kind]}</span>
      <code>{entry.region.node_path}</code>
      <small>
        {entry.region.start} - {entry.region.end ?? "-"}
      </small>
      {entry.relation !== "normal" && <em>{entry.relation}</em>}
    </>
  );

  return (
    <button
      className={className}
      type="button"
      style={{
        height: `${bounds.height}px`,
        left: getLaneLeft(laneIndex),
        top: `${bounds.top}px`,
        width: "calc(33.333333% - 4px)",
      }}
      onClick={() => onSelectRegion?.(entry.region.node_path)}
      aria-label={`Select address region ${entry.region.node_path}`}
    >
      {content}
    </button>
  );
}

function buildAddressSpaceModel(regions: MemoryRegion[]) {
  const normalized = regions
    .map(normalizeRegion)
    .filter((region): region is NormalizedRegion => region !== null)
    .sort(compareNormalizedRegions);
  const entries: AddressSpaceEntry[] = [];
  const gaps: AddressSpaceGapEntry[] = [];
  const regionEntries: AddressSpaceRegionEntry[] = [];
  let coverageEnd: bigint | null = null;

  for (const item of normalized) {
    let relation: RegionRelation = "normal";

    if (coverageEnd === null) {
      if (item.start > 0n) {
        addGap(0n, item.start - 1n);
      }
    } else if (item.start > coverageEnd + 1n) {
      addGap(coverageEnd + 1n, item.start - 1n);
    } else if (item.start <= coverageEnd) {
      relation = item.end <= coverageEnd ? "nested" : "overlap";
    }

    const regionEntry: AddressSpaceRegionEntry = {
      entryKind: "region",
      region: item.region,
      start: item.start,
      end: item.end,
      size: item.size,
      relation,
    };

    entries.push(regionEntry);
    regionEntries.push(regionEntry);

    if (coverageEnd === null || item.end > coverageEnd) {
      coverageEnd = item.end;
    }
  }

  const range = getModelRange(regionEntries);

  return {
    entries,
    gaps,
    range,
    regions: regionEntries,
  };

  function addGap(start: bigint, end: bigint) {
    const gap: AddressSpaceGapEntry = {
      entryKind: "gap",
      start,
      end,
      size: end - start + 1n,
    };
    entries.push(gap);
    gaps.push(gap);
  }
}

function normalizeRegion(
  region: MemoryRegion,
  order: number,
): NormalizedRegion | null {
  const start = parseAddress(region.start);

  if (start === null) {
    return null;
  }

  const parsedEnd = parseAddress(region.end);
  const parsedSize = parseAddress(region.size);
  const end =
    parsedEnd ?? (parsedSize === null || parsedSize === 0n ? start : start + parsedSize - 1n);

  return {
    order,
    region,
    start,
    end,
    size: parsedSize,
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
  if (left.end !== right.end) {
    return left.end > right.end ? -1 : 1;
  }

  return left.order - right.order;
}

function getModelRange(regions: AddressSpaceRegionEntry[]): AddressSpaceRange {
  if (regions.length === 0) {
    return { start: 0n, end: 0n, span: 1n };
  }

  const firstStart = regions[0].start;
  const start = firstStart < 0n ? firstStart : 0n;
  const end = regions.reduce(
    (current, region) => (region.end > current ? region.end : current),
    start,
  );

  return {
    start,
    end,
    span: end - start + 1n,
  };
}

function getViewportRange(
  fullRange: AddressSpaceRange,
  zoom: number,
  pan: number,
): AddressSpaceRange {
  const clampedZoom = clampZoom(zoom);
  const viewportSpan = fullRange.span / BigInt(clampedZoom);
  const span = viewportSpan > 0n ? viewportSpan : 1n;
  const maxStart = fullRange.end - span + 1n;
  const available = maxStart > fullRange.start ? maxStart - fullRange.start : 0n;
  const start = fullRange.start + (available * BigInt(clampPan(pan))) / 1000n;
  const end = start + span - 1n;

  return {
    start,
    end: end > fullRange.end ? fullRange.end : end,
    span,
  };
}

function getPanForCenter(
  fullRange: AddressSpaceRange,
  zoom: number,
  center: bigint,
  viewportSpan: bigint,
): number {
  const maxStart = fullRange.end - viewportSpan + 1n;
  const available = maxStart > fullRange.start ? maxStart - fullRange.start : 0n;

  if (available === 0n) {
    return 0;
  }

  const unclampedStart = center - viewportSpan / 2n;
  const start =
    unclampedStart < fullRange.start
      ? fullRange.start
      : unclampedStart > maxStart
        ? maxStart
        : unclampedStart;

  return Number(((start - fullRange.start) * 1000n) / available);
}

function getFitSelectedZoom(
  fullRange: AddressSpaceRange,
  region: AddressSpaceRegionEntry,
): number {
  const regionSize = region.end - region.start + 1n;
  const numerator = BigInt(TARGET_SELECTED_HEIGHT) * fullRange.span;
  const denominator = BigInt(VIEWPORT_HEIGHT) * regionSize;
  const requested = (numerator + denominator - 1n) / denominator;

  if (requested > BigInt(MAX_ZOOM)) {
    return MAX_ZOOM;
  }

  return clampZoom(Number(requested));
}

function getRegionCenter(region: AddressSpaceRegionEntry): bigint {
  return region.start + (region.end - region.start) / 2n;
}

function getVisibleBounds(
  start: bigint,
  end: bigint,
  viewport: AddressSpaceRange,
  minimumHeight: number,
) {
  const visibleStart = start > viewport.start ? start : viewport.start;
  const visibleEnd = end < viewport.end ? end : viewport.end;
  const top = getAddressY(visibleStart, viewport);
  const rawHeight = Number(
    ((visibleEnd - visibleStart + 1n) * BigInt(VIEWPORT_HEIGHT)) /
      viewport.span,
  );

  return {
    height: Math.max(minimumHeight, rawHeight),
    top,
  };
}

function getAddressY(address: bigint, viewport: AddressSpaceRange): number {
  if (address <= viewport.start) {
    return 0;
  }

  if (address >= viewport.end) {
    return VIEWPORT_HEIGHT;
  }

  return Number(
    ((address - viewport.start) * BigInt(VIEWPORT_HEIGHT)) / viewport.span,
  );
}

function getTickAddresses(viewport: AddressSpaceRange): bigint[] {
  return [0n, 1n, 2n, 3n, 4n].map(
    (index) => viewport.start + (viewport.span * index) / 4n,
  );
}

function intersects(
  entry: Pick<AddressSpaceEntry, "start" | "end">,
  viewport: AddressSpaceRange,
): boolean {
  return entry.start <= viewport.end && entry.end >= viewport.start;
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

function clampZoom(value: number): number {
  return Math.max(1, Math.min(MAX_ZOOM, value));
}

function clampPan(value: number): number {
  return Math.max(0, Math.min(1000, value));
}

function formatZoom(zoom: number): string {
  return `${zoom.toLocaleString()}x`;
}

function getLaneLeft(laneIndex: number): string {
  return laneIndex === 0
    ? "0"
    : `calc(${(laneIndex * 100) / 3}% + ${laneIndex * 2}px)`;
}

function formatHex(value: bigint): string {
  return `0x${value.toString(16)}`;
}
