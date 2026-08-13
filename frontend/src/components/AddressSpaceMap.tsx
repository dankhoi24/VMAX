import { useEffect, useMemo, useState } from "react";

import type { MemoryRegion } from "../models/addressing";
import { CursorIcon, HandIcon } from "./icons";

type RegionRelation = "normal" | "nested" | "overlap";
type RegionDisplayMode = "full" | "compact" | "marker";
type GapDisplayMode = "full" | "compact" | "marker";
type InteractionMode = "default" | "hand";

type NormalizedRegion =
  | {
      entryKind: "region";
      order: number;
      region: MemoryRegion;
      start: bigint;
      end: bigint;
      size: bigint | null;
    }
  | {
      entryKind: "unknown";
      order: number;
      region: MemoryRegion;
      start: bigint;
    };

interface AddressSpaceRange {
  start: bigint;
  end: bigint;
  span: bigint;
}

interface ViewportState {
  start: bigint;
  span: bigint;
}

interface PointerGesture {
  pointerId: number;
  startY: number;
  initialViewportStart: bigint;
  initialViewportSpan: bigint;
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

export interface AddressSpaceUnknownEntry {
  entryKind: "unknown";
  region: MemoryRegion;
  start: bigint;
}

export type AddressSpaceEntry =
  | AddressSpaceGapEntry
  | AddressSpaceRegionEntry
  | AddressSpaceUnknownEntry;

interface RegionRenderItem {
  entry: AddressSpaceRegionEntry;
  bounds: VisibleBounds;
  displayMode: RegionDisplayMode;
  isSelected: boolean;
  laneIndex: number;
}

interface RegionCluster {
  entryKind: "cluster";
  count: number;
  items: RegionRenderItem[];
  laneIndex: number;
  range: AddressSpaceRange;
  top: number;
  height: number;
}

type RegionRenderGroup =
  | { entryKind: "item"; item: RegionRenderItem }
  | RegionCluster;

interface VisibleBounds {
  hitHeight: number;
  hitTop: number;
  visualHeight: number;
  visualTop: number;
}

interface AddressSpaceMapProps {
  regions: MemoryRegion[];
  selectedNodePath?: string | null;
  focusRequest?: number;
  onSelectRegion?: (nodePath: string) => void;
}

const KIND_LANES: MemoryRegion["kind"][] = ["ram", "reserved", "device"];
const HITBOX_HEIGHT = 14;
const MIN_VISUAL_HEIGHT = 1;
const REGION_COMPACT_HEIGHT = 8;
const REGION_FULL_HEIGHT = 32;
const GAP_COMPACT_HEIGHT = 10;
const GAP_FULL_HEIGHT = 40;
const CLUSTER_DISTANCE = 14;
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
  focusRequest = 0,
  onSelectRegion,
}: AddressSpaceMapProps) {
  const model = useMemo(() => buildAddressSpaceModel(regions), [regions]);
  const selectedRegions = useMemo(
    () =>
      model.regions.filter(
        (entry) => entry.region.node_path === selectedNodePath,
      ),
    [model.regions, selectedNodePath],
  );
  const selectedRange = useMemo(
    () => getSelectedRange(model.regions, selectedNodePath),
    [model.regions, selectedNodePath],
  );
  const [selectedResourceIndex, setSelectedResourceIndex] = useState<
    number | null
  >(null);
  const [interactionMode, setInteractionMode] =
    useState<InteractionMode>("default");
  const [viewportState, setViewportState] = useState<ViewportState | null>(null);
  const [drag, setDrag] = useState<PointerGesture | null>(null);
  const [expandedClusterKey, setExpandedClusterKey] = useState<string | null>(
    null,
  );
  const viewport = clampViewport(
    model.range,
    viewportState ?? getFullViewport(model.range),
  );
  const selectedFocusRange = useMemo(
    () =>
      selectedResourceIndex !== null && selectedRegions[selectedResourceIndex]
        ? entryToRange(selectedRegions[selectedResourceIndex])
        : selectedRange,
    [selectedRange, selectedRegions, selectedResourceIndex],
  );

  useEffect(() => {
    setExpandedClusterKey(null);
    setViewportState(getFullViewport(model.range));
  }, [model.range.start, model.range.end]);

  useEffect(() => {
    setSelectedResourceIndex(selectedRegions.length > 1 ? 0 : null);
  }, [selectedNodePath, selectedRegions.length]);

  useEffect(() => {
    if (selectedFocusRange) {
      setExpandedClusterKey(null);
      setViewportState(fitRangeViewport(model.range, selectedFocusRange));
    }
  }, [focusRequest, model.range, selectedFocusRange]);

  if (model.regions.length === 0 && model.unknowns.length === 0) {
    return (
      <p className="addressing-empty-text">
        No CPU physical address regions described.
      </p>
    );
  }

  function fitAll() {
    setExpandedClusterKey(null);
    setViewportState(getFullViewport(model.range));
  }

  function fitSelected() {
    if (selectedFocusRange) {
      setExpandedClusterKey(null);
      setViewportState(fitRangeViewport(model.range, selectedFocusRange));
    }
  }

  function fitSelectedNode() {
    if (selectedRange) {
      setSelectedResourceIndex(null);
      setExpandedClusterKey(null);
      setViewportState(fitRangeViewport(model.range, selectedRange));
    }
  }

  function fitSelectedResource(index: number) {
    const region = selectedRegions[index];

    if (region) {
      setSelectedResourceIndex(index);
      setExpandedClusterKey(null);
      setViewportState(fitRangeViewport(model.range, entryToRange(region)));
    }
  }

  function fitCluster(cluster: RegionCluster) {
    if (isInseparableCluster(cluster)) {
      const clusterKey = getClusterKey(cluster);
      setExpandedClusterKey((current) =>
        current === clusterKey ? null : clusterKey,
      );
      return;
    }

    setExpandedClusterKey(null);
    setViewportState(
      zoomIntoClusterViewport(model.range, viewport, cluster.range),
    );
  }

  function zoomBy(factor: bigint) {
    const center = viewport.start + viewport.span / 2n;
    const nextSpan =
      factor < 0n
        ? viewport.span * -factor
        : ceilDiv(viewport.span, factor);

    setExpandedClusterKey(null);
    setViewportState(getCenteredViewport(model.range, center, nextSpan));
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (interactionMode !== "hand") {
      return;
    }

    if (event.button > 0) {
      return;
    }

    event.currentTarget.setPointerCapture?.(event.pointerId);

    setDrag({
      initialViewportSpan: viewport.span,
      initialViewportStart: viewport.start,
      pointerId: event.pointerId,
      startY: getPointerClientY(event, PLOT_HEIGHT / 2),
    });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }

    const deltaPixels = Math.round(
      getPointerClientY(event, drag.startY) - drag.startY,
    );

    const deltaAddress =
      (BigInt(deltaPixels) * drag.initialViewportSpan) / PLOT_HEIGHT_BIGINT;

    setExpandedClusterKey(null);
    setViewportState(
      clampViewport(model.range, {
        start: drag.initialViewportStart - deltaAddress,
        span: drag.initialViewportSpan,
      }),
    );
  }

  function handlePointerEnd(event: React.PointerEvent<HTMLDivElement>) {
    if (drag?.pointerId === event.pointerId) {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      }
      setDrag(null);
    }
  }

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();

    if (interactionMode !== "hand") {
      scrollViewport(event.deltaY);
      return;
    }

    const anchorPixelY = getWheelPixelY(event);
    const anchorAddress = getAddressAtPixel(anchorPixelY, viewport);
    const nextSpan =
      event.deltaY > 0 ? viewport.span * 2n : ceilDiv(viewport.span, 2n);

    setExpandedClusterKey(null);
    setViewportState(
      getAnchoredViewport(model.range, anchorAddress, anchorPixelY, nextSpan),
    );
  }

  function scrollViewport(deltaY: number) {
    const pixels = Math.trunc(deltaY);

    if (pixels === 0) {
      return;
    }

    const deltaAddress =
      (viewport.span * BigInt(pixels)) / PLOT_HEIGHT_BIGINT;

    setExpandedClusterKey(null);
    setViewportState(
      clampViewport(model.range, {
        start: viewport.start + deltaAddress,
        span: viewport.span,
      }),
    );
  }

  const visibleGaps = model.gaps.filter((gap) => intersects(gap, viewport));
  const visibleRegions = model.regions.filter((region) =>
    intersects(region, viewport),
  );
  const visibleUnknowns = model.unknowns.filter((entry) =>
    pointIntersects(entry.start, viewport),
  );
  const regionGroups = clusterRegionItems(
    visibleRegions.map((entry) => {
      const bounds = getVisibleBounds(entry.start, entry.end, viewport);

      return {
        bounds,
        displayMode: getRegionDisplayMode(bounds.visualHeight),
        entry,
        isSelected: entry.region.node_path === selectedNodePath,
        laneIndex: KIND_LANES.indexOf(entry.region.kind),
      };
    }),
  );
  const tickAddresses = getTickAddresses(viewport);
  const plotClassName = [
    "address-space-plot",
    `address-space-plot-${interactionMode}`,
    drag ? `address-space-plot-${interactionMode}-dragging` : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="address-space-map">
      <div className="address-space-toolbar" aria-label="Address space controls">
        <div className="address-space-tool-group" aria-label="Interaction mode">
          <span className="address-space-toolbar-label">Interaction</span>
          <button
            className={
              interactionMode === "default"
                ? "address-space-mode-button address-space-mode-button-active"
                : "address-space-mode-button"
            }
            type="button"
            aria-label="Default"
            aria-pressed={interactionMode === "default"}
            title="Scroll normally and select regions"
            onClick={() => setInteractionMode("default")}
          >
            <CursorIcon className="address-space-tool-icon" />
          </button>
          <button
            className={
              interactionMode === "hand"
                ? "address-space-mode-button address-space-mode-button-active"
                : "address-space-mode-button"
            }
            type="button"
            aria-label="Hand"
            aria-pressed={interactionMode === "hand"}
            title="Wheel to zoom, drag to pan"
            onClick={() => setInteractionMode("hand")}
          >
            <HandIcon className="address-space-tool-icon" />
          </button>
        </div>
        <div className="address-space-tool-group" aria-label="Viewport controls">
          <button type="button" onClick={() => zoomBy(-2n)}>
            -
          </button>
          <span className="address-space-span-chip">
            {formatSpan(viewport.span)}
          </span>
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
      </div>

      {selectedRegions.length > 1 && (
        <div
          className="address-space-resource-controls"
          aria-label="Selected node address resources"
        >
          {selectedRegions.map((region, index) => (
            <button
              className={
                selectedResourceIndex === index
                  ? "address-space-resource-button address-space-resource-button-active"
                  : "address-space-resource-button"
              }
              key={`${region.region.node_path}:${region.region.start}:${index}`}
              type="button"
              onClick={() => fitSelectedResource(index)}
            >
              Resource {index}
            </button>
          ))}
          <button
            className={
              selectedResourceIndex === null
                ? "address-space-resource-button address-space-resource-button-active"
                : "address-space-resource-button"
            }
            type="button"
            onClick={fitSelectedNode}
          >
            Fit Node
          </button>
        </div>
      )}

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
            className={plotClassName}
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

              {visibleUnknowns.map((entry, index) => (
                <AddressSpaceUnknown
                  entry={entry}
                  key={`${entry.region.node_path}:${entry.region.start}:${index}`}
                  viewport={viewport}
                />
              ))}

              {regionGroups.map((group, index) =>
                group.entryKind === "cluster" ? (
                  <AddressSpaceCluster
                    cluster={group}
                    key={`cluster:${group.laneIndex}:${group.range.start}:${index}`}
                    isExpanded={expandedClusterKey === getClusterKey(group)}
                    onFitCluster={fitCluster}
                    onSelectRegion={(nodePath) => {
                      setExpandedClusterKey(null);
                      onSelectRegion?.(nodePath);
                    }}
                  />
                ) : (
                  <AddressSpaceRegion
                    item={group.item}
                    key={`${group.item.entry.region.node_path}:${group.item.entry.region.start}:${index}`}
                    onSelectRegion={onSelectRegion}
                  />
                ),
              )}
            </div>
          </div>
        </div>
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
  const displayMode = getGapDisplayMode(bounds.visualHeight);

  return (
    <div
      className={`address-space-gap-band address-space-gap-band-${displayMode}`}
      style={{
        height: `${bounds.visualHeight}px`,
        top: `${bounds.visualTop}px`,
      }}
    >
      {displayMode !== "marker" && <span>GAP</span>}
      {displayMode === "full" && (
        <code>
          {formatHex(gap.start)} - {formatHex(gap.end)}
        </code>
      )}
    </div>
  );
}

function AddressSpaceRegion({
  item,
  onSelectRegion,
}: {
  item: RegionRenderItem;
  onSelectRegion?: (nodePath: string) => void;
}) {
  const { bounds, displayMode, entry, isSelected, laneIndex } = item;
  const relationshipText =
    entry.relation === "normal" ? null : `Relationship: ${entry.relation}`;
  const className = [
    "address-space-region-hitbox",
    `address-space-region-hitbox-${entry.region.kind}`,
    `address-space-region-hitbox-${entry.relation}`,
    `address-space-region-hitbox-${displayMode}`,
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
      title={[
        entry.region.node_path,
        `${entry.region.start} - ${entry.region.end ?? "unknown"}`,
        relationshipText,
      ]
        .filter(Boolean)
        .join("\n")}
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
      {displayMode !== "marker" && (
        <span className="address-space-region-label">
          <code>{entry.region.node_path}</code>
        </span>
      )}
      {displayMode === "full" && (
        <small>
          {entry.region.start} - {entry.region.end ?? "-"}
        </small>
      )}
      {displayMode === "marker" && (
        <span className="address-space-region-callout">
          <strong>{entry.region.node_path}</strong>
          <code>
            {entry.region.start} - {entry.region.end ?? "-"}
          </code>
          <span>Size: {entry.region.size ?? "-"}</span>
          {relationshipText && <span>{relationshipText}</span>}
        </span>
      )}
    </button>
  );
}

function AddressSpaceCluster({
  cluster,
  isExpanded,
  onFitCluster,
  onSelectRegion,
}: {
  cluster: RegionCluster;
  isExpanded: boolean;
  onFitCluster: (cluster: RegionCluster) => void;
  onSelectRegion?: (nodePath: string) => void;
}) {
  return (
    <>
      <button
        className={
          isExpanded
            ? "address-space-cluster address-space-cluster-expanded"
            : "address-space-cluster"
        }
        type="button"
        style={{
          height: `${cluster.height}px`,
          left: getLaneLeft(cluster.laneIndex),
          top: `${cluster.top}px`,
          width: "calc(33.333333% - 4px)",
        }}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          onFitCluster(cluster);
        }}
        aria-label={`Zoom into ${cluster.count} address regions`}
        title={`${cluster.count} regions\n${formatHex(cluster.range.start)} - ${formatHex(cluster.range.end)}`}
      >
        <span className="address-space-cluster-count">+{cluster.count}</span>
      </button>
      {isExpanded && (
        <div
          className="address-space-cluster-popover"
          style={{
            left: getLaneLeft(cluster.laneIndex),
            top: `${getClusterPopoverTop(cluster)}px`,
            width: "calc(33.333333% - 4px)",
          }}
          onPointerDown={(event) => event.stopPropagation()}
          role="group"
          aria-label={`${cluster.count} clustered address regions`}
        >
          <strong>{cluster.count} regions</strong>
          <code>
            {formatHex(cluster.range.start)} - {formatHex(cluster.range.end)}
          </code>
          <ul>
            {cluster.items.map((item, index) => (
              <li
                key={`${item.entry.region.node_path}:${item.entry.region.start}:${index}`}
              >
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectRegion?.(item.entry.region.node_path);
                  }}
                >
                  <span>{item.entry.region.node_path}</span>
                  <code>
                    {item.entry.region.start} - {item.entry.region.end ?? "-"}
                  </code>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function AddressSpaceUnknown({
  entry,
  viewport,
}: {
  entry: AddressSpaceUnknownEntry;
  viewport: AddressSpaceRange;
}) {
  const top = getAddressY(entry.start, viewport);
  const laneIndex = KIND_LANES.indexOf(entry.region.kind);

  return (
    <div
      className={`address-space-unknown address-space-unknown-${entry.region.kind}`}
      style={{
        left: getLaneLeft(laneIndex),
        top: `${top}px`,
        width: "calc(33.333333% - 4px)",
      }}
      title={`${entry.region.node_path}\n${entry.region.start} - unknown`}
    >
      <span>unknown</span>
    </div>
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
  const unknownEntries: AddressSpaceUnknownEntry[] = [];
  let coverageEnd: bigint | null = null;
  let coverageUnknown = false;

  for (const item of normalized) {
    if (item.entryKind === "unknown") {
      if (coverageEnd === null && !coverageUnknown && item.start > 0n) {
        addGap(0n, item.start - 1n);
      } else if (
        coverageEnd !== null &&
        !coverageUnknown &&
        item.start > coverageEnd + 1n
      ) {
        addGap(coverageEnd + 1n, item.start - 1n);
      }

      const unknownEntry: AddressSpaceUnknownEntry = {
        entryKind: "unknown",
        region: item.region,
        start: item.start,
      };
      entries.push(unknownEntry);
      unknownEntries.push(unknownEntry);
      coverageUnknown = true;
      continue;
    }

    let relation: RegionRelation = "normal";

    if (coverageEnd === null) {
      if (!coverageUnknown && item.start > 0n) {
        addGap(0n, item.start - 1n);
      }
    } else if (!coverageUnknown && item.start > coverageEnd + 1n) {
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
  const fullRange = includeUnknownsInRange(range, unknownEntries);

  return {
    entries,
    gaps,
    range: fullRange,
    regions: regionEntries,
    unknowns: unknownEntries,
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

  if (end === null) {
    return {
      entryKind: "unknown",
      order,
      region,
      start,
    };
  }

  if (end < start) {
    return null;
  }

  return {
    entryKind: "region",
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
  const leftEnd = left.entryKind === "region" ? left.end : left.start;
  const rightEnd = right.entryKind === "region" ? right.end : right.start;
  if (leftEnd !== rightEnd) {
    return leftEnd > rightEnd ? -1 : 1;
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

function includeUnknownsInRange(
  range: AddressSpaceRange,
  unknowns: AddressSpaceUnknownEntry[],
): AddressSpaceRange {
  if (unknowns.length === 0) {
    return range;
  }

  const start = unknowns.reduce(
    (current, entry) => (entry.start < current ? entry.start : current),
    range.start,
  );
  const end = unknowns.reduce(
    (current, entry) => (entry.start > current ? entry.start : current),
    range.end,
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

function entryToRange(entry: AddressSpaceRegionEntry): AddressSpaceRange {
  return {
    start: entry.start,
    end: entry.end,
    span: entry.end - entry.start + 1n,
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

function zoomIntoClusterViewport(
  fullRange: AddressSpaceRange,
  viewport: AddressSpaceRange,
  clusterRange: AddressSpaceRange,
): ViewportState {
  const quarterViewport = viewport.span > 4n ? viewport.span / 4n : 1n;
  const minimumSpan = clusterRange.span > 1n ? clusterRange.span * 2n : 1n;
  let nextSpan =
    quarterViewport > minimumSpan ? quarterViewport : minimumSpan;

  if (nextSpan >= viewport.span) {
    nextSpan = viewport.span > 1n ? ceilDiv(viewport.span, 2n) : 1n;
  }

  const center = clusterRange.start + clusterRange.span / 2n;

  return getCenteredViewport(fullRange, center, nextSpan);
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

function getAnchoredViewport(
  fullRange: AddressSpaceRange,
  anchorAddress: bigint,
  anchorPixelY: number,
  requestedSpan: bigint,
): ViewportState {
  const pixel = BigInt(clampPlotPixel(anchorPixelY));
  const span =
    requestedSpan < 1n
      ? 1n
      : requestedSpan > fullRange.span
        ? fullRange.span
        : requestedSpan;

  return clampViewport(fullRange, {
    start: anchorAddress - (span * pixel) / PLOT_HEIGHT_BIGINT,
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

function clusterRegionItems(items: RegionRenderItem[]): RegionRenderGroup[] {
  const groups: RegionRenderGroup[] = [];

  for (const laneIndex of [0, 1, 2]) {
    const laneItems = items
      .filter((item) => item.laneIndex === laneIndex)
      .sort((left, right) => left.bounds.visualTop - right.bounds.visualTop);
    let pending: RegionRenderItem[] = [];

    for (const item of laneItems) {
      if (shouldCluster(item)) {
        const last = pending[pending.length - 1];
        if (
          pending.length > 0 &&
          item.bounds.visualTop - getClusterBottom(pending) <= CLUSTER_DISTANCE
        ) {
          pending.push(item);
          continue;
        }

        flushPending();
        pending = [item];
        continue;
      }

      flushPending();
      groups.push({ entryKind: "item", item });
    }

    flushPending();

    function flushPending() {
      if (pending.length === 0) {
        return;
      }

      if (pending.length === 1) {
        groups.push({ entryKind: "item", item: pending[0] });
      } else {
        groups.push(buildCluster(laneIndex, pending));
      }

      pending = [];
    }
  }

  return groups.sort((left, right) => getGroupTop(left) - getGroupTop(right));
}

function shouldCluster(item: RegionRenderItem): boolean {
  return item.displayMode === "marker" && !item.isSelected;
}

function buildCluster(
  laneIndex: number,
  items: RegionRenderItem[],
): RegionCluster {
  const start = items.reduce(
    (current, item) => (item.entry.start < current ? item.entry.start : current),
    items[0].entry.start,
  );
  const end = items.reduce(
    (current, item) => (item.entry.end > current ? item.entry.end : current),
    items[0].entry.end,
  );
  const top = items.reduce(
    (current, item) =>
      item.bounds.hitTop < current ? item.bounds.hitTop : current,
    items[0].bounds.hitTop,
  );
  const bottom = items.reduce((current, item) => {
    const itemBottom = item.bounds.hitTop + item.bounds.hitHeight;
    return itemBottom > current ? itemBottom : current;
  }, items[0].bounds.hitTop + items[0].bounds.hitHeight);

  return {
    count: items.length,
    entryKind: "cluster",
    height: Math.max(HITBOX_HEIGHT, bottom - top),
    items,
    laneIndex,
    range: {
      start,
      end,
      span: end - start + 1n,
    },
    top,
  };
}

function isInseparableCluster(cluster: RegionCluster): boolean {
  return cluster.items.every(
    (item) =>
      item.entry.start === cluster.items[0].entry.start &&
      item.entry.end === cluster.items[0].entry.end,
  );
}

function getClusterKey(cluster: RegionCluster): string {
  return [
    cluster.laneIndex,
    cluster.range.start.toString(),
    cluster.range.end.toString(),
    cluster.items.map((item) => item.entry.region.node_path).join("|"),
  ].join(":");
}

function getClusterPopoverTop(cluster: RegionCluster): number {
  return clampPixel(cluster.top + cluster.height + 6, 0, PLOT_HEIGHT - 120);
}

function getClusterBottom(items: RegionRenderItem[]): number {
  return items.reduce((current, item) => {
    const bottom = item.bounds.hitTop + item.bounds.hitHeight;
    return bottom > current ? bottom : current;
  }, 0);
}

function getGroupTop(group: RegionRenderGroup): number {
  return group.entryKind === "cluster" ? group.top : group.item.bounds.hitTop;
}

function getRegionDisplayMode(height: number): RegionDisplayMode {
  if (height >= REGION_FULL_HEIGHT) {
    return "full";
  }
  if (height >= REGION_COMPACT_HEIGHT) {
    return "compact";
  }
  return "marker";
}

function getGapDisplayMode(height: number): GapDisplayMode {
  if (height >= GAP_FULL_HEIGHT) {
    return "full";
  }
  if (height >= GAP_COMPACT_HEIGHT) {
    return "compact";
  }
  return "marker";
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

function getAddressAtPixel(pixelY: number, viewport: AddressSpaceRange): bigint {
  if (pixelY <= 0) {
    return viewport.start;
  }

  if (pixelY >= PLOT_HEIGHT) {
    return viewport.end;
  }

  return (
    viewport.start +
    (viewport.span * BigInt(clampPlotPixel(pixelY))) / PLOT_HEIGHT_BIGINT
  );
}

function getWheelPixelY(event: React.WheelEvent<HTMLDivElement>): number {
  return getElementPixelY(event.clientY, event.currentTarget);
}

function getElementPixelY(clientY: number, element: HTMLDivElement): number {
  const rect = element.getBoundingClientRect();
  const rectTop = Number.isFinite(rect.top) ? rect.top : 0;
  const safeClientY = Number.isFinite(clientY)
    ? clientY
    : rectTop + PLOT_HEIGHT / 2;

  return clampPlotPixel(safeClientY - rectTop);
}

function getPointerClientY(
  event: React.PointerEvent<HTMLDivElement>,
  fallback: number,
): number {
  return Number.isFinite(event.clientY) ? event.clientY : fallback;
}

function clampPlotPixel(value: number): number {
  if (!Number.isFinite(value)) {
    return Math.floor(PLOT_HEIGHT / 2);
  }

  return Math.round(clampPixel(value, 0, PLOT_HEIGHT));
}

function getTickAddresses(viewport: AddressSpaceRange): bigint[] {
  return [0n, 1n, 2n, 3n, 4n].map(
    (index) => viewport.start + (viewport.span * index) / 4n,
  );
}

function intersects(
  entry: Pick<AddressSpaceGapEntry | AddressSpaceRegionEntry, "start" | "end">,
  viewport: AddressSpaceRange,
): boolean {
  return entry.start <= viewport.end && entry.end >= viewport.start;
}

function pointIntersects(point: bigint, viewport: AddressSpaceRange): boolean {
  return point >= viewport.start && point <= viewport.end;
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
