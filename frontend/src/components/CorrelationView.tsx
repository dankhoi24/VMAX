import { useEffect, useMemo, useState } from "react";

import { ApiError, getCorrelationDevices } from "../api/correlation";
import type {
  AddressCorrelation,
  AddressMatchType,
  CorrelatedDevice,
  CorrelationDevicesResponse,
  CorrelationMatchMethod,
  CorrelationWarning,
  StaticAddressRegion,
} from "../models/correlation";
import { AddressingIcon, SearchIcon, WarningIcon, XIcon } from "./icons";

type CorrelationState =
  | { status: "loading" }
  | { status: "success"; response: CorrelationDevicesResponse }
  | { status: "error"; message: string; detail: string[] };

type StatusFilter = "all" | CorrelationMatchMethod;

const emptyCorrelations: CorrelatedDevice[] = [];
const statusFilters: StatusFilter[] = [
  "all",
  "exact_of_node",
  "unmatched",
  "unavailable",
];
const driverBindingReadFailedCode = "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED";

export function CorrelationView() {
  const [state, setState] = useState<CorrelationState>({ status: "loading" });
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    void getCorrelationDevices().then(
      (response) => {
        if (isMounted) {
          setState({ status: "success", response });
          setSelectedKey((current) => current ?? getCorrelationKey(response.data[0]));
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
  }, []);

  const correlations =
    state.status === "success" ? state.response.data : emptyCorrelations;
  const warnings = state.status === "success" ? state.response.warnings : [];
  const trimmedQuery = query.trim();
  const filteredCorrelations = useMemo(
    () => filterCorrelations(correlations, trimmedQuery, statusFilter),
    [correlations, statusFilter, trimmedQuery],
  );
  const selectedCorrelation =
    filteredCorrelations.find(
      (correlation) => getCorrelationKey(correlation) === selectedKey,
    ) ?? null;

  useEffect(() => {
    if (state.status !== "success") {
      return;
    }

    if (
      selectedKey !== null &&
      filteredCorrelations.some(
        (correlation) => getCorrelationKey(correlation) === selectedKey,
      )
    ) {
      return;
    }

    setSelectedKey(getCorrelationKey(filteredCorrelations[0]));
  }, [filteredCorrelations, selectedKey, state.status]);

  return (
    <section className="correlation-view" aria-label="Correlation devices">
      <div className="correlation-header">
        <div className="panel-title">
          <AddressingIcon className="panel-icon" />
          <h2>DT Runtime Correlation</h2>
        </div>
        {state.status === "success" && (
          <span>{correlations.length.toLocaleString()} relations</span>
        )}
      </div>

      {state.status === "loading" && (
        <div className="runtime-browser-status" aria-live="polite">
          Loading correlation data...
        </div>
      )}

      {state.status === "error" && (
        <div
          className="runtime-browser-status runtime-browser-error"
          aria-live="polite"
        >
          <h3>Unable to load correlation data</h3>
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
          <CorrelationSummary correlations={correlations} warnings={warnings} />
          {warnings.length > 0 && <CorrelationWarnings warnings={warnings} />}
          <div className="correlation-body">
            <div className="correlation-list-panel">
              <div className="runtime-search-shell">
                <SearchIcon className="runtime-search-icon" />
                <input
                  aria-label="Search correlations"
                  className="runtime-search-input"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search DT path, device, driver..."
                />
                {query.length > 0 && (
                  <button
                    className="runtime-search-clear-button"
                    type="button"
                    aria-label="Clear correlation search"
                    title="Clear search"
                    onClick={() => setQuery("")}
                  >
                    <XIcon className="search-clear-icon" />
                  </button>
                )}
              </div>
              <CorrelationFilters
                activeFilter={statusFilter}
                correlations={correlations}
                onChange={setStatusFilter}
              />
              {correlations.length === 0 ? (
                <p className="runtime-empty">
                  No correlation rows reported by the current source.
                </p>
              ) : filteredCorrelations.length === 0 ? (
                <p className="runtime-empty">No matching correlations.</p>
              ) : (
                <ul
                  className="correlation-list"
                  aria-label="Correlation device list"
                >
                  {filteredCorrelations.map((correlation) => {
                    const key = getCorrelationKey(correlation);
                    return (
                      <li key={key}>
                        <button
                          className={getCorrelationButtonClassName(
                            selectedKey === key,
                          )}
                          type="button"
                          aria-pressed={selectedKey === key}
                          onClick={() => setSelectedKey(key)}
                        >
                          <span className="correlation-row-main">
                            <span className="correlation-row-title">
                              {getCorrelationTitle(correlation)}
                            </span>
                            <MatchMethodBadge method={correlation.match_method} />
                          </span>
                          <span className="correlation-row-meta">
                            {formatRuntimeSummary(correlation, warnings)}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <CorrelationDetails
              correlation={selectedCorrelation}
              warnings={warnings}
            />
          </div>
        </>
      )}
    </section>
  );
}

interface CorrelationSummaryProps {
  correlations: CorrelatedDevice[];
  warnings: CorrelationWarning[];
}

function CorrelationSummary({
  correlations,
  warnings,
}: CorrelationSummaryProps) {
  return (
    <dl className="correlation-summary">
      <SummaryItem label="exact" value={countByMethod(correlations, "exact_of_node")} />
      <SummaryItem label="unmatched" value={countByMethod(correlations, "unmatched")} />
      <SummaryItem
        label="unavailable"
        value={countByMethod(correlations, "unavailable")}
      />
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

interface CorrelationFiltersProps {
  activeFilter: StatusFilter;
  correlations: CorrelatedDevice[];
  onChange: (filter: StatusFilter) => void;
}

function CorrelationFilters({
  activeFilter,
  correlations,
  onChange,
}: CorrelationFiltersProps) {
  return (
    <div className="correlation-filter-row" aria-label="Correlation filters">
      {statusFilters.map((filter) => (
        <button
          key={filter}
          className={
            activeFilter === filter
              ? "correlation-filter correlation-filter-active"
              : "correlation-filter"
          }
          type="button"
          aria-pressed={activeFilter === filter}
          onClick={() => onChange(filter)}
        >
          {formatFilterLabel(filter)}
          <span>{countForFilter(correlations, filter).toLocaleString()}</span>
        </button>
      ))}
    </div>
  );
}

interface CorrelationWarningsProps {
  warnings: CorrelationWarning[];
}

function CorrelationWarnings({ warnings }: CorrelationWarningsProps) {
  return (
    <ul className="runtime-warning-list" aria-label="Correlation warnings">
      {warnings.map((warning) => (
        <li key={getWarningKey(warning)}>
          <WarningIcon className="warning-icon" />
          <div>
            <strong>{warning.code}</strong>
            <p>{warning.message}</p>
            {warning.dt_node_path && <code>{warning.dt_node_path}</code>}
            {warning.runtime_device_path && (
              <code>{warning.runtime_device_path}</code>
            )}
            {warning.source_path && <code>{warning.source_path}</code>}
          </div>
        </li>
      ))}
    </ul>
  );
}

interface CorrelationDetailsProps {
  correlation: CorrelatedDevice | null;
  warnings: CorrelationWarning[];
}

function CorrelationDetails({ correlation, warnings }: CorrelationDetailsProps) {
  if (!correlation) {
    return (
      <aside className="correlation-detail" aria-label="Correlation detail">
        <div className="runtime-detail-empty">Select a correlation row.</div>
      </aside>
    );
  }

  return (
    <aside className="correlation-detail" aria-label="Correlation detail">
      <div className="correlation-detail-heading">
        <code>{getCorrelationTitle(correlation)}</code>
        <MatchMethodBadge method={correlation.match_method} />
      </div>

      <section className="correlation-detail-section">
        <h3>Identity</h3>
        <dl className="correlation-field-grid">
          <CorrelationField label="DT node" value={correlation.dt_node_path} />
          <CorrelationField
            label="method"
            value={formatMatchMethod(correlation.match_method)}
          />
        </dl>
      </section>

      <section className="correlation-detail-section">
        <h3>Linux Runtime</h3>
        <dl className="correlation-field-grid">
          <CorrelationField
            label="device"
            value={formatRuntimeDeviceName(correlation)}
          />
          <CorrelationField
            label="device path"
            value={correlation.runtime_device?.sysfs_path ?? null}
          />
          <CorrelationField
            label="of_node"
            value={correlation.runtime_device?.of_node_sysfs_path ?? null}
          />
          <CorrelationField
            label="driver binding"
            value={formatDriverBindingName(correlation, warnings)}
          />
          <CorrelationField
            label="binding path"
            value={formatDriverBindingPath(correlation)}
          />
          <CorrelationField
            label="driver inventory"
            value={formatDriverInventoryState(correlation, warnings)}
          />
          <CorrelationField
            label="driver detail path"
            value={correlation.runtime_driver?.sysfs_path ?? null}
          />
        </dl>
      </section>

      <section className="correlation-detail-section">
        <h3>Static DT Ranges</h3>
        <StaticRangeList regions={correlation.static_regions} />
      </section>

      <section className="correlation-detail-section">
        <h3>/proc/iomem Relation</h3>
        <AddressMatchList matches={correlation.address_matches} />
      </section>

      {correlation.warnings.length > 0 && (
        <section className="correlation-detail-section">
          <h3>Warnings</h3>
          <CorrelationWarnings warnings={correlation.warnings} />
        </section>
      )}
    </aside>
  );
}

interface CorrelationFieldProps {
  label: string;
  value: string | null;
}

function CorrelationField({ label, value }: CorrelationFieldProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "-"}</code>
      </dd>
    </div>
  );
}

interface StaticRangeListProps {
  regions: StaticAddressRegion[];
}

function StaticRangeList({ regions }: StaticRangeListProps) {
  if (regions.length === 0) {
    return (
      <p className="correlation-empty">
        No translated DT physical ranges for this row.
      </p>
    );
  }

  return (
    <ul className="correlation-card-list" aria-label="Static DT ranges">
      {regions.map((region) => (
        <li key={`${region.node_path}:${region.bus_address}:${region.cpu_start}`}>
          <article className="correlation-card">
            <div className="correlation-card-heading">
              <strong>DT PA</strong>
              <code>{formatNullableRange(region.cpu_start, region.cpu_end)}</code>
            </div>
            <dl className="correlation-field-grid correlation-field-grid-compact">
              <CorrelationField label="node" value={region.node_path} />
              <CorrelationField label="bus" value={region.bus_address} />
              <CorrelationField label="size" value={region.size} />
            </dl>
          </article>
        </li>
      ))}
    </ul>
  );
}

interface AddressMatchListProps {
  matches: AddressCorrelation[];
}

function AddressMatchList({ matches }: AddressMatchListProps) {
  if (matches.length === 0) {
    return (
      <p className="correlation-empty">
        No resolved address relation for this row.
      </p>
    );
  }

  return (
    <ul className="correlation-card-list" aria-label="Address correlations">
      {matches.map((match) => (
        <li key={`${match.dt_start}:${match.dt_end}:${match.match_type}`}>
          <article className="correlation-card">
            <div className="correlation-card-heading">
              <AddressMatchBadge matchType={match.match_type} />
              <span>{describeAddressMatch(match.match_type)}</span>
            </div>
            <dl className="correlation-field-grid correlation-field-grid-compact">
              <CorrelationField
                label="DT PA"
                value={formatNullableRange(match.dt_start, match.dt_end)}
              />
              <CorrelationField
                label="iomem"
                value={formatIomemRange(match)}
              />
              <CorrelationField label="name" value={match.iomem_name} />
            </dl>
            {match.candidates.length > 1 && (
              <CandidateList candidates={match.candidates} />
            )}
          </article>
        </li>
      ))}
    </ul>
  );
}

interface CandidateListProps {
  candidates: AddressCorrelation["candidates"];
}

function CandidateList({ candidates }: CandidateListProps) {
  return (
    <div className="correlation-candidates">
      <strong>Candidates</strong>
      <ul>
        {candidates.map((candidate) => (
          <li key={`${candidate.start}:${candidate.end}:${candidate.name}`}>
            <code>{formatNullableRange(candidate.start, candidate.end)}</code>
            <span>{candidate.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface MatchMethodBadgeProps {
  method: CorrelationMatchMethod;
}

function MatchMethodBadge({ method }: MatchMethodBadgeProps) {
  return (
    <span className={`correlation-badge correlation-badge-${method}`}>
      {formatMatchMethod(method)}
    </span>
  );
}

interface AddressMatchBadgeProps {
  matchType: AddressMatchType;
}

function AddressMatchBadge({ matchType }: AddressMatchBadgeProps) {
  return (
    <span className={`correlation-badge correlation-address-${matchType}`}>
      {formatAddressMatch(matchType)}
    </span>
  );
}

function filterCorrelations(
  correlations: CorrelatedDevice[],
  query: string,
  statusFilter: StatusFilter,
): CorrelatedDevice[] {
  const byStatus =
    statusFilter === "all"
      ? correlations
      : correlations.filter(
          (correlation) => correlation.match_method === statusFilter,
        );

  if (!query) {
    return byStatus;
  }

  const needle = query.toLowerCase();
  return byStatus.filter((correlation) =>
    getSearchFields(correlation).some((value) =>
      value.toLowerCase().includes(needle),
    ),
  );
}

function getSearchFields(correlation: CorrelatedDevice): string[] {
  return [
    correlation.dt_node_path,
    correlation.runtime_device?.name,
    correlation.runtime_device?.sysfs_path,
    correlation.runtime_device?.driver_name,
    correlation.runtime_driver?.name,
    correlation.runtime_driver?.sysfs_path,
    correlation.match_method,
    ...correlation.static_regions.flatMap((region) => [
      region.node_path,
      region.bus_address,
      region.cpu_start,
      region.cpu_end,
    ]),
    ...correlation.address_matches.flatMap((match) => [
      match.dt_start,
      match.dt_end,
      match.iomem_start,
      match.iomem_end,
      match.iomem_name,
      match.match_type,
      ...match.candidates.flatMap((candidate) => [
        candidate.name,
        candidate.start,
        candidate.end,
      ]),
    ]),
    ...correlation.warnings.flatMap((warning) => [
      warning.code,
      warning.message,
      warning.source_path,
    ]),
  ].filter((value): value is string => Boolean(value));
}

function countByMethod(
  correlations: CorrelatedDevice[],
  method: CorrelationMatchMethod,
): number {
  return correlations.filter((correlation) => correlation.match_method === method)
    .length;
}

function countForFilter(
  correlations: CorrelatedDevice[],
  filter: StatusFilter,
): number {
  return filter === "all" ? correlations.length : countByMethod(correlations, filter);
}

function getCorrelationKey(correlation: CorrelatedDevice | undefined): string | null {
  if (!correlation) {
    return null;
  }

  return [
    correlation.dt_node_path ?? "-",
    correlation.runtime_device?.sysfs_path ?? "-",
    correlation.match_method,
  ].join("|");
}

function getCorrelationTitle(correlation: CorrelatedDevice): string {
  return (
    correlation.dt_node_path ??
    correlation.runtime_device?.name ??
    correlation.runtime_device?.sysfs_path ??
    "unidentified correlation"
  );
}

function formatRuntimeSummary(
  correlation: CorrelatedDevice,
  warnings: CorrelationWarning[],
): string {
  const device = formatRuntimeDeviceName(correlation) ?? "no runtime device";
  const driver = formatDriverBindingName(correlation, warnings) ?? "no driver";
  return `${device} / ${driver}`;
}

function formatRuntimeDeviceName(correlation: CorrelatedDevice): string | null {
  if (correlation.runtime_device !== null) {
    return correlation.runtime_device.name;
  }

  return correlation.match_method === "unavailable"
    ? "runtime device unknown"
    : null;
}

function formatDriverBindingName(
  correlation: CorrelatedDevice,
  warnings: CorrelationWarning[],
): string | null {
  if (correlation.runtime_device?.driver_name) {
    return correlation.runtime_device.driver_name;
  }

  if (correlation.runtime_driver !== null) {
    return correlation.runtime_driver.name;
  }

  if (correlation.runtime_device !== null) {
    return isDriverBindingReadFailed(correlation, warnings)
      ? "unknown"
      : "unbound";
  }

  return correlation.match_method === "unavailable" ? "driver unknown" : null;
}

function formatDriverBindingPath(correlation: CorrelatedDevice): string | null {
  return (
    correlation.runtime_device?.driver_path ??
    correlation.runtime_driver?.sysfs_path ??
    null
  );
}

function formatDriverInventoryState(
  correlation: CorrelatedDevice,
  warnings: CorrelationWarning[],
): string {
  if (correlation.runtime_driver !== null) {
    return "available";
  }

  if (
    correlation.runtime_device?.driver_name ||
    correlation.runtime_device?.driver_path
  ) {
    return "driver details unavailable";
  }

  if (correlation.runtime_device !== null) {
    return isDriverBindingReadFailed(correlation, warnings)
      ? "driver binding unknown"
      : "unbound";
  }

  return correlation.match_method === "unavailable"
    ? "unknown"
    : "no runtime device";
}

function isDriverBindingReadFailed(
  correlation: CorrelatedDevice,
  warnings: CorrelationWarning[],
): boolean {
  const device = correlation.runtime_device;
  if (device === null) {
    return false;
  }

  const driverPath = `${device.sysfs_path}/driver`;
  return [...warnings, ...correlation.warnings].some(
    (warning) =>
      warning.code === driverBindingReadFailedCode &&
      warning.source_path === driverPath,
  );
}

function formatFilterLabel(filter: StatusFilter): string {
  return filter === "all" ? "all" : formatMatchMethod(filter).toLowerCase();
}

function formatMatchMethod(method: CorrelationMatchMethod): string {
  if (method === "exact_of_node") {
    return "EXACT OF_NODE";
  }

  return method.toUpperCase();
}

function formatAddressMatch(matchType: AddressMatchType): string {
  return matchType.replaceAll("_", " ").toUpperCase();
}

function describeAddressMatch(matchType: AddressMatchType): string {
  switch (matchType) {
    case "exact":
      return "DT physical range equals a /proc/iomem range.";
    case "iomem_contains_dt":
      return "/proc/iomem contains the DT physical range.";
    case "dt_contains_iomem":
      return "DT physical range contains a /proc/iomem range.";
    case "overlap":
      return "Partial overlap; treat as a weak relation.";
    case "none":
      return "Source scan completed and no relation was found.";
    case "ambiguous":
      return "Multiple /proc/iomem candidates match this DT range.";
    case "unavailable":
      return "Source data is incomplete, so no negative conclusion is made.";
  }
}

function formatNullableRange(start: string | null, end: string | null): string | null {
  if (start === null || end === null) {
    return null;
  }

  return `${start} - ${end}`;
}

function formatIomemRange(match: AddressCorrelation): string | null {
  return formatNullableRange(match.iomem_start, match.iomem_end);
}

function getCorrelationButtonClassName(isSelected: boolean): string {
  return isSelected
    ? "correlation-button correlation-button-selected"
    : "correlation-button";
}

function getWarningKey(warning: CorrelationWarning): string {
  return [
    warning.code,
    warning.dt_node_path,
    warning.runtime_device_path,
    warning.source_path,
    warning.message,
  ].join(":");
}

function toErrorState(error: unknown): CorrelationState {
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
