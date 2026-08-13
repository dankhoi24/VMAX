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

interface ViewportState {
  start: bigint;
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
const HITBOX_HEIGHT = 14;
const MIN_VISUAL_HEIGHT = 1;
const PLOT_HEIGHT = 520;
const PLOT_HEIGHT_BIGINT = BigInt(PLOT_HEIGHT);

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
  const selectedRange = useMemo(
    () => getSelectedRange(model.regions, selectedNodePath),
    [model.regions, selectedNodePath],
  );
  const [viewportState, setViewportState] = useState<ViewportState | null>(null);
  const [drag, setDrag] = useState<{
    pointerId: number;
    startY: number;
    viewportStart: bigint;
  } | null>(null);
  const viewport = clampViewport(
    model.range,
    viewportState ?? getFullViewport(model.range),
  );
  const panPercent = getPanPercent(model.range, viewport);

  useEffect(() => {
    setViewportState(getFullViewport(model.range));
  }, [model.range.start, model.range.end]);

  useEffect(() => {
    if (selectedRange) {
      setViewportState(fitRangeViewport(model.range, selectedRange));
    }
  }, [model.range, selectedRange]);

  if (model.regions.length === 0) {
    return (
      <p className="addressing-empty-text">
        No CPU physical address regions described.
      </p>
    );
  }

  function fitAll() {
    setViewportState(getFullViewport(model.range));
  }

  function fitSelected() {
    if (selectedRange) {
      setViewportState(fitRangeViewport(model.range, selectedRange));
    }
  }

  function zoomBy(factor: bigint) {
    const center = viewport.start + viewport.span / 2n;
    const nextSpan =
      factor < 0n
        ? viewport.span * -factor
        : ceilDiv(viewport.span, factor);

    setViewportState(getCenteredViewport(model.range, center, nextSpan));
  }

  function updatePan(nextPanPercent: number) {
    const available = getPanAvailable(model.range, viewport.span);

    if (available === 0n) {
      setViewportState(getFullViewport(model.range));
      return;
    }

    setViewportState(
      clampViewport(model.range, {
        start:
          model.range.start +
          (available * BigInt(clampPercent(nextPanPercent))) / 1000n,
        span: viewport.span,
      }),
    );
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? -2n : 2n);
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({
      pointerId: event.pointerId,
      startY: event.clientY,
      viewportStart: viewport.start,
    });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }

    const deltaPixels = Math.round(event.clientY - drag.startY);
    const deltaAddress = (BigInt(deltaPixels) * viewport.span) / PLOT_HEIGHT_BIGINT;

    setViewportState(
      clampViewport(model.range, {
        start: drag.viewportStart - deltaAddress,
        span: viewport.span,
      }),
    );
  }

  function handlePointerEnd(event: React.PointerEvent<HTMLDivElement>) {
    if (drag?.pointerId === event.pointerId) {
      setDrag(null);
    }
  }

  const visibleGaps = model.gaps.filter((gap) => intersects(gap, viewport));
  const visibleRegions = model.regions.filter((region) =>
    intersects(region, viewport),
  );
  const tickAddresses = getTickAddresses(viewport);

  return (
    <div className="address-space-map">
      <div className="address-space-toolbar" aria-label="Address space controls">
        <button type="button" onClick={() => zoomBy(-2n)}>
          -
        </button>
        <span>{formatSpan(viewport.span)}</span>
        <button type="button" onClick={() => zoomBy(2n)}>
          +
        </button>
        <button type="button" onClick={fitAll}>
          Fit All
        </button>
        <button type="button" onClick={fitSelected} disabled={!selectedRange}>
          Fit Selected
        </button>
      </div>

      <div className="address-space-window">
        <div className="address-space-readout" aria-label="Visible address range">
          <code>{formatHex(viewport.start)}</code>
          <span>-</span>
          <code>{formatHex(viewport.end)}</code>
        </div>

        <div className="address-space-viewport">
          <div className="address-space-header">
            <span>Address</span>
            {KIND_LANES.map((kind) => (
              <span key={kind}>{REGION_LABELS[kind]}</span>
            ))}
          </div>

          <div
            className={drag ? "address-space-plot address-space-plot-dragging" : "address-space-plot"}
            aria-label="CPU Physical Address Space"
            onWheel={handleWheel}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerEnd}
            onPointerCancel={handlePointerEnd}
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

            <div className="address-space-plot-lanes">
              {KIND_LANES.map((kind) => (
                <div className="address-space-lane" key={kind} />
              ))}

              {visibleGaps.map((gap) => (
                <AddressSpaceGap
                  gap={gap}
                  key={`gap:${gap.start.toString()}:${gap.end.toString()}`}
                  viewport={viewport}
                />
              ))}

              {visibleRegions.map((entry, index) => (
                <AddressSpaceRegion
                  entry={entry}
                  isSelected={entry.region.node_path === selectedNodePath}
                  key={`${entry.region.node_path}:${entry.region.start}:${index}`}
                  onSelectRegion={onSelectRegion}
                  viewport={viewport}
                />
              ))}
            </div>
          </div>
        </div>

        <label className="address-space-pan">
          <span>Pan</span>
          <input
            type="range"
            min="0"
            max="1000"
            value={panPercent}
            onChange={(event) => updatePan(Number(event.target.value))}
            disabled={viewport.span >= model.range.span}
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
  const bounds = getVisibleBounds(gap.start, gap.end, viewport);

  return (
    <div
      className="address-space-gap-band"
      style={{
        height: `${bounds.visualHeight}px`,
        top: `${bounds.visualTop}px`,
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
  const bounds = getVisibleBounds(entry.start, entry.end, viewport);
  const laneIndex = KIND_LANES.indexOf(entry.region.kind);
  const className = [
    "address-space-region-hitbox",
    `address-space-region-hitbox-${entry.region.kind}`,
    `address-space-region-hitbox-${entry.relation}`,
    isSelected ? "address-space-region-hitbox-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      className={className}
      type="button"
      style={{
        height: `${bounds.hitHeight}px`,
        left: getLaneLeft(laneIndex),
        top: `${bounds.hitTop}px`,
        width: "calc(33.333333% - 4px)",
      }}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        onSelectRegion?.(entry.region.node_path);
      }}
      aria-label={`Select address region ${entry.region.node_path}`}
      title={`${entry.region.node_path}\n${entry.region.start} - ${entry.region.end ?? "unknown"}`}
    >
      <span
        className={[
          "address-space-region-geometry",
          `address-space-region-geometry-${entry.region.kind}`,
          `address-space-region-geometry-${entry.relation}`,
        ].join(" ")}
        style={{
          height: `${bounds.visualHeight}px`,
          top: `${bounds.visualTop - bounds.hitTop}px`,
        }}
      />
      <span className="address-space-region-label">
        <strong>{REGION_LABELS[entry.region.kind]}</strong>
        <code>{entry.region.node_path}</code>
        {entry.relation !== "normal" && <em>{entry.relation}</em>}
      </span>
      <small>
        {entry.region.start} - {entry.region.end ?? "-"}
      </small>
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
  const parsedEnd = parseAddress(region.end);
  const parsedSize = parseAddress(region.size);

  if (start === null) {
    return null;
  }

  const end =
    parsedEnd ??
    (parsedSize === null || parsedSize === 0n
      ? null
      : start + parsedSize - 1n);

  if (end === null || end < start) {
    return null;
  }

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

function getSelectedRange(
  regions: AddressSpaceRegionEntry[],
  selectedNodePath: string | null,
): AddressSpaceRange | null {
  const selected = regions.filter(
    (entry) => entry.region.node_path === selectedNodePath,
  );

  if (selected.length === 0) {
    return null;
  }

  const start = selected.reduce(
    (current, entry) => (entry.start < current ? entry.start : current),
    selected[0].start,
  );
  const end = selected.reduce(
    (current, entry) => (entry.end > current ? entry.end : current),
    selected[0].end,
  );

  return {
    start,
    end,
    span: end - start + 1n,
  };
}

function getFullViewport(range: AddressSpaceRange): ViewportState {
  return {
    start: range.start,
    span: range.span,
  };
}

function fitRangeViewport(
  fullRange: AddressSpaceRange,
  targetRange: AddressSpaceRange,
): ViewportState {
  const requestedSpan = targetRange.span * 6n;
  const span = requestedSpan > fullRange.span ? fullRange.span : requestedSpan;
  const center = targetRange.start + targetRange.span / 2n;

  return getCenteredViewport(fullRange, center, span);
}

function getCenteredViewport(
  fullRange: AddressSpaceRange,
  center: bigint,
  requestedSpan: bigint,
): ViewportState {
  const span =
    requestedSpan < 1n
      ? 1n
      : requestedSpan > fullRange.span
        ? fullRange.span
        : requestedSpan;

  return clampViewport(fullRange, {
    start: center - span / 2n,
    span,
  });
}

function clampViewport(
  fullRange: AddressSpaceRange,
  viewport: ViewportState,
): AddressSpaceRange {
  const span =
    viewport.span < 1n
      ? 1n
      : viewport.span > fullRange.span
        ? fullRange.span
        : viewport.span;
  const maxStart = fullRange.end - span + 1n;
  const start =
    viewport.start < fullRange.start
      ? fullRange.start
      : viewport.start > maxStart
        ? maxStart
        : viewport.start;
  const end = start + span - 1n;

  return {
    start,
    end,
    span,
  };
}

function getPanAvailable(
  fullRange: AddressSpaceRange,
  viewportSpan: bigint,
): bigint {
  return fullRange.span > viewportSpan ? fullRange.span - viewportSpan : 0n;
}

function getPanPercent(
  fullRange: AddressSpaceRange,
  viewport: AddressSpaceRange,
): number {
  const available = getPanAvailable(fullRange, viewport.span);

  if (available === 0n) {
    return 0;
  }

  return Number(((viewport.start - fullRange.start) * 1000n) / available);
}

function getVisibleBounds(
  start: bigint,
  end: bigint,
  viewport: AddressSpaceRange,
) {
  const visibleStart = start > viewport.start ? start : viewport.start;
  const visibleEnd = end < viewport.end ? end : viewport.end;
  const visualTop = getAddressY(visibleStart, viewport);
  const rawHeight = Number(
    ((visibleEnd - visibleStart + 1n) * PLOT_HEIGHT_BIGINT) / viewport.span,
  );
  const visualHeight = Math.max(MIN_VISUAL_HEIGHT, rawHeight);
  const hitHeight = Math.max(HITBOX_HEIGHT, visualHeight);
  const hitTop = clampPixel(
    visualTop - Math.floor((hitHeight - visualHeight) / 2),
    0,
    PLOT_HEIGHT - hitHeight,
  );

  return {
    hitHeight,
    hitTop,
    visualHeight,
    visualTop,
  };
}

function getAddressY(address: bigint, viewport: AddressSpaceRange): number {
  if (address <= viewport.start) {
    return 0;
  }

  if (address >= viewport.end) {
    return PLOT_HEIGHT;
  }

  return Number(
    ((address - viewport.start) * PLOT_HEIGHT_BIGINT) / viewport.span,
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

function ceilDiv(dividend: bigint, divisor: bigint): bigint {
  return (dividend + divisor - 1n) / divisor;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(1000, value));
}

function clampPixel(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function formatSpan(span: bigint): string {
  return `span ${formatHex(span)}`;
}

function getLaneLeft(laneIndex: number): string {
  return laneIndex === 0
    ? "0"
    : `calc(${(laneIndex * 100) / 3}% + ${laneIndex * 2}px)`;
}

function formatHex(value: bigint): string {
  return `0x${value.toString(16)}`;
}
