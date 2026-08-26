import { useEffect, useMemo, useState } from "react";

import { ApiError, getDependencyDevices } from "../api/dependencies";
import type {
  DependencyDevicesResponse,
  DependencyKind,
  DependencyWarning,
  DeviceDependency,
  DeviceDependencyView,
} from "../models/dependency";
import { AddressingIcon, SearchIcon, XIcon } from "./icons";
import { DependencySection } from "./DependencySection";
import { DependencyWarnings } from "./DependencyRow";

type DependencyState =
  | { status: "loading" }
  | { status: "success"; response: DependencyDevicesResponse }
  | { status: "error"; message: string; detail: string[] };

const emptyViews: DeviceDependencyView[] = [];
const dependencyKinds: DependencyKind[] = [
  "clock",
  "reset",
  "power_domain",
  "dma",
  "iommu",
  "interrupt",
];

interface DependencyPanelProps {
  refreshToken?: number;
}

export function DependencyPanel({ refreshToken = 0 }: DependencyPanelProps) {
  const [state, setState] = useState<DependencyState>({ status: "loading" });
  const [query, setQuery] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setState({ status: "loading" });

    void getDependencyDevices().then(
      (response) => {
        if (isMounted) {
          setState({ status: "success", response });
          setSelectedPath((current) => current ?? response.data[0]?.dt_node_path ?? null);
        }
      },
      (error: unknown) => {
        if (isMounted) {
          setState(toErrorState(error));
        }
      },
    );

    return () => {
      isMounted = false;
    };
  }, [refreshToken]);

  const views = state.status === "success" ? state.response.data : emptyViews;
  const warnings = state.status === "success" ? state.response.warnings : [];
  const trimmedQuery = query.trim();
  const filteredViews = useMemo(
    () => filterDependencyViews(views, trimmedQuery),
    [trimmedQuery, views],
  );
  const selectedView =
    filteredViews.find((view) => view.dt_node_path === selectedPath) ?? null;

  useEffect(() => {
    if (state.status !== "success") {
      return;
    }

    const nextSelectedPath = filteredViews[0]?.dt_node_path ?? null;
    if (
      selectedPath !== null &&
      filteredViews.some((view) => view.dt_node_path === selectedPath)
    ) {
      return;
    }

    if (selectedPath !== nextSelectedPath) {
      setSelectedPath(nextSelectedPath);
    }
  }, [filteredViews, selectedPath, state.status]);

  return (
    <section className="dependency-panel" aria-label="Device dependencies">
      <div className="dependency-header">
        <div className="panel-title">
          <AddressingIcon className="panel-icon" />
          <h2>Device Dependencies</h2>
        </div>
        {state.status === "success" && (
          <span>{countDependencies(views).toLocaleString()} dependencies</span>
        )}
      </div>

      {state.status === "loading" && (
        <div className="runtime-browser-status" aria-live="polite">
          Loading device dependencies...
        </div>
      )}

      {state.status === "error" && (
        <div
          className="runtime-browser-status runtime-browser-error"
          aria-live="polite"
        >
          <h3>Unable to load device dependencies</h3>
          <p>{state.message}</p>
          {state.detail.length > 0 && (
            <ul>
              {state.detail.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {state.status === "success" && (
        <>
          <DependencySummary views={views} warnings={warnings} />
          {warnings.length > 0 && (
            <DependencyWarnings
              label="Dependency warnings"
              warnings={warnings}
            />
          )}
          <div className="dependency-body">
            <div className="dependency-list-panel">
              <div className="runtime-search-shell">
                <SearchIcon className="runtime-search-icon" />
                <input
                  aria-label="Search dependencies"
                  className="runtime-search-input"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search DT path, provider, IRQ..."
                />
                {query.length > 0 && (
                  <button
                    className="runtime-search-clear-button"
                    type="button"
                    aria-label="Clear dependency search"
                    title="Clear search"
                    onClick={() => setQuery("")}
                  >
                    <XIcon className="search-clear-icon" />
                  </button>
                )}
              </div>

              {views.length === 0 ? (
                <p className="runtime-empty">
                  No dependency views reported by the current source.
                </p>
              ) : filteredViews.length === 0 ? (
                <p className="runtime-empty">No matching dependencies.</p>
              ) : (
                <ul
                  className="dependency-device-list"
                  aria-label="Dependency device list"
                >
                  {filteredViews.map((view) => (
                    <li key={view.dt_node_path}>
                      <button
                        className={getDependencyButtonClassName(
                          selectedPath === view.dt_node_path,
                        )}
                        type="button"
                        aria-pressed={selectedPath === view.dt_node_path}
                        onClick={() => setSelectedPath(view.dt_node_path)}
                      >
                        <span className="dependency-device-row-main">
                          <span className="dependency-device-path">
                            {view.dt_node_path}
                          </span>
                          <span className="dependency-count-badge">
                            {view.dependencies.length.toLocaleString()}
                          </span>
                        </span>
                        <span className="dependency-device-row-meta">
                          {formatDependencyKindSummary(view.dependencies)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <DependencyDetails view={selectedView} />
          </div>
        </>
      )}
    </section>
  );
}

interface DependencySummaryProps {
  views: DeviceDependencyView[];
  warnings: DependencyWarning[];
}

function DependencySummary({ views, warnings }: DependencySummaryProps) {
  return (
    <dl className="dependency-summary">
      <SummaryItem label="devices" value={views.length} />
      <SummaryItem label="dependencies" value={countDependencies(views)} />
      <SummaryItem label="interrupts" value={countByKind(views, "interrupt")} />
      <SummaryItem label="warnings" value={warnings.length} />
    </dl>
  );
}

interface SummaryItemProps {
  label: string;
  value: number;
}

function SummaryItem({ label, value }: SummaryItemProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value.toLocaleString()}</dd>
    </div>
  );
}

interface DependencyDetailsProps {
  view: DeviceDependencyView | null;
}

function DependencyDetails({ view }: DependencyDetailsProps) {
  if (!view) {
    return (
      <aside className="dependency-detail" aria-label="Dependency detail">
        <div className="runtime-detail-empty">Select a dependency device.</div>
      </aside>
    );
  }

  return (
    <aside className="dependency-detail" aria-label="Dependency detail">
      <div className="dependency-detail-heading">
        <code>{view.dt_node_path}</code>
        <span className="dependency-count-badge">
          {view.dependencies.length.toLocaleString()}
        </span>
      </div>
      {dependencyKinds.map((kind) => (
        <DependencySection
          key={kind}
          kind={kind}
          dependencies={view.dependencies.filter(
            (dependency) => dependency.kind === kind,
          )}
        />
      ))}
    </aside>
  );
}

function filterDependencyViews(
  views: DeviceDependencyView[],
  query: string,
): DeviceDependencyView[] {
  if (!query) {
    return views;
  }

  const needle = query.toLowerCase();
  return views.filter((view) =>
    getSearchFields(view).some((value) =>
      value.toLowerCase().includes(needle),
    ),
  );
}

function getSearchFields(view: DeviceDependencyView): string[] {
  return [
    view.dt_node_path,
    ...view.dependencies.flatMap((dependency) => [
      dependency.kind,
      dependency.consumer_dt_path,
      dependency.provider_dt_path,
      dependency.provider_phandle?.toString(),
      dependency.name,
      dependency.source_property,
      dependency.static_resolution,
      dependency.interrupt_resolution,
      dependency.interrupt_match_method,
      ...dependency.specifier_cells.map((cell) => cell.toString()),
      dependency.runtime_interrupt?.irq.toString(),
      dependency.runtime_interrupt?.controller,
      dependency.runtime_interrupt?.hardware_irq?.toString(),
      ...(dependency.runtime_interrupt?.actions ?? []),
      ...dependency.runtime_candidates.flatMap((candidate) => [
        candidate.irq.toString(),
        candidate.controller,
        candidate.hardware_irq?.toString(),
        ...candidate.actions,
      ]),
      ...dependency.interrupt_warnings.flatMap((warning) => [
        warning.code,
        warning.message,
        warning.source_path,
      ]),
    ]),
  ].filter((value): value is string => Boolean(value));
}

function countDependencies(views: DeviceDependencyView[]): number {
  return views.reduce((total, view) => total + view.dependencies.length, 0);
}

function countByKind(
  views: DeviceDependencyView[],
  kind: DependencyKind,
): number {
  return views.reduce(
    (total, view) =>
      total +
      view.dependencies.filter((dependency) => dependency.kind === kind).length,
    0,
  );
}

function formatDependencyKindSummary(dependencies: DeviceDependency[]): string {
  const counts = dependencyKinds
    .map((kind) => ({
      kind,
      count: dependencies.filter((dependency) => dependency.kind === kind)
        .length,
    }))
    .filter((item) => item.count > 0);

  if (counts.length === 0) {
    return "no dependencies";
  }

  return counts
    .map((item) => `${item.count} ${item.kind.replaceAll("_", " ")}`)
    .join(" / ");
}

function getDependencyButtonClassName(isSelected: boolean): string {
  return isSelected
    ? "dependency-device-button dependency-device-button-selected"
    : "dependency-device-button";
}

function toErrorState(error: unknown): DependencyState {
  if (error instanceof ApiError) {
    return {
      status: "error",
      message: error.message,
      detail: error.detail?.errors ?? [],
    };
  }

  if (error instanceof Error) {
    return {
      status: "error",
      message: error.message,
      detail: [],
    };
  }

  return {
    status: "error",
    message: "Unknown error",
    detail: [],
  };
}
