import type {
  DependencyRuntimeInterrupt,
  DependencyWarning,
  DeviceDependency,
} from "../models/dependency";
import { formatHex } from "../models/runtime";
import { WarningIcon } from "./icons";

interface DependencyRowProps {
  dependency: DeviceDependency;
}

export function DependencyRow({ dependency }: DependencyRowProps) {
  return (
    <article className="dependency-row">
      <div className="dependency-row-header">
        <div>
          <strong>{formatKind(dependency.kind)}</strong>
          <span>{formatDependencySubtitle(dependency)}</span>
        </div>
        <div className="dependency-status-pair">
          <StatusBadge label="Static" value={dependency.static_resolution} />
          {dependency.kind === "interrupt" && (
            <StatusBadge
              label="Runtime"
              value={dependency.interrupt_resolution ?? "unavailable"}
            />
          )}
        </div>
      </div>

      <dl className="dependency-field-grid">
        <DependencyField label="Provider" value={dependency.provider_dt_path} />
        <DependencyField
          label="Provider phandle"
          value={formatNullableNumber(dependency.provider_phandle)}
        />
        <DependencyField
          label="Entry"
          value={dependency.entry_index.toString()}
        />
        <DependencyField label="Name" value={dependency.name} />
        <DependencyField
          label="Source"
          value={dependency.source_property}
        />
        <DependencyField
          label="Specifier"
          value={formatSpecifier(dependency.specifier_cells)}
        />
      </dl>

      {dependency.evidence.length > 0 && (
        <EvidenceList evidence={dependency.evidence} />
      )}

      {dependency.kind === "interrupt" && (
        <RuntimeInterruptRelation dependency={dependency} />
      )}

      {dependency.interrupt_warnings.length > 0 && (
        <DependencyWarnings
          label="Dependency warnings"
          warnings={dependency.interrupt_warnings}
        />
      )}
    </article>
  );
}

interface StatusBadgeProps {
  label: string;
  value: string;
}

function StatusBadge({ label, value }: StatusBadgeProps) {
  return (
    <span
      className={`dependency-status dependency-status-${value.replaceAll(
        "_",
        "-",
      )}`}
    >
      <span>{label}</span>
      {formatResolution(value)}
    </span>
  );
}

interface DependencyFieldProps {
  label: string;
  value: string | null;
}

function DependencyField({ label, value }: DependencyFieldProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "-"}</code>
      </dd>
    </div>
  );
}

interface EvidenceListProps {
  evidence: DeviceDependency["evidence"];
}

function EvidenceList({ evidence }: EvidenceListProps) {
  return (
    <div className="dependency-evidence">
      <strong>Evidence</strong>
      <ul>
        {evidence.map((item) => (
          <li key={`${item.kind}:${item.source}:${item.source_path ?? ""}`}>
            <span>{item.kind.toUpperCase()}</span>
            <code>{item.source_path ?? item.source}</code>
            {item.message && <small>{item.message}</small>}
          </li>
        ))}
      </ul>
    </div>
  );
}

interface RuntimeInterruptRelationProps {
  dependency: DeviceDependency;
}

function RuntimeInterruptRelation({ dependency }: RuntimeInterruptRelationProps) {
  const showCandidates =
    dependency.interrupt_resolution === "ambiguous" &&
    dependency.runtime_candidates.length > 0;

  return (
    <section className="dependency-runtime-block">
      <div className="dependency-runtime-heading">
        <strong>Runtime IRQ</strong>
        <code>{dependency.interrupt_match_method ?? "-"}</code>
      </div>

      {dependency.runtime_interrupt ? (
        <RuntimeInterruptCard interrupt={dependency.runtime_interrupt} />
      ) : (
        <p className="dependency-empty">
          Runtime interrupt data is not resolved for this dependency.
        </p>
      )}

      {showCandidates && (
        <div className="dependency-candidates">
          <strong>Candidates</strong>
          <ul>
            {dependency.runtime_candidates.map((candidate) => (
              <li key={candidate.irq}>
                <RuntimeInterruptCard interrupt={candidate} compact />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

interface RuntimeInterruptCardProps {
  interrupt: DependencyRuntimeInterrupt;
  compact?: boolean;
}

function RuntimeInterruptCard({
  interrupt,
  compact = false,
}: RuntimeInterruptCardProps) {
  return (
    <dl
      className={
        compact
          ? "dependency-interrupt-card dependency-interrupt-card-compact"
          : "dependency-interrupt-card"
      }
    >
      <DependencyField label="Linux IRQ" value={interrupt.irq.toString()} />
      <DependencyField
        label="HWIRQ"
        value={formatNullableAddress(interrupt.hardware_irq)}
      />
      <DependencyField label="Controller" value={interrupt.controller} />
      <DependencyField label="Trigger" value={interrupt.trigger} />
      <DependencyField label="Actions" value={formatList(interrupt.actions)} />
      <DependencyField
        label="Count"
        value={interrupt.total_count.toLocaleString()}
      />
      {!compact && (
        <DependencyField label="Source" value={interrupt.source_path} />
      )}
    </dl>
  );
}

interface DependencyWarningsProps {
  label: string;
  warnings: DependencyWarning[];
}

export function DependencyWarnings({ label, warnings }: DependencyWarningsProps) {
  return (
    <ul className="runtime-warning-list" aria-label={label}>
      {warnings.map((warning) => (
        <li key={getWarningKey(warning)}>
          <WarningIcon className="warning-icon" />
          <div>
            <strong>{warning.code}</strong>
            <p>{warning.message}</p>
            {warning.consumer_dt_path && <code>{warning.consumer_dt_path}</code>}
            {warning.provider_dt_path && <code>{warning.provider_dt_path}</code>}
            {warning.runtime_irq !== null && (
              <code>IRQ {warning.runtime_irq}</code>
            )}
            {warning.source_path && <code>{warning.source_path}</code>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function formatDependencySubtitle(dependency: DeviceDependency): string {
  const provider = dependency.provider_dt_path ?? "provider unknown";
  const source = dependency.source_property ?? "unknown source";
  return `${source} -> ${provider}`;
}

function formatKind(kind: string): string {
  return kind.replaceAll("_", " ").toUpperCase();
}

function formatResolution(value: string): string {
  return value.replaceAll("_", " ").toUpperCase();
}

function formatNullableNumber(value: number | null): string | null {
  return value === null ? null : value.toString();
}

function formatNullableAddress(value: number | null): string | null {
  return value === null ? null : `${value.toString()} (${formatHex(value)})`;
}

function formatSpecifier(cells: number[]): string {
  if (cells.length === 0) {
    return "<>";
  }

  return `<${cells.map((cell) => formatHex(cell)).join(" ")}>`;
}

function formatList(values: string[]): string | null {
  return values.length === 0 ? null : values.join(", ");
}

function getWarningKey(warning: DependencyWarning): string {
  return [
    warning.code,
    warning.consumer_dt_path,
    warning.provider_dt_path,
    warning.runtime_irq,
    warning.source_path,
    warning.message,
  ].join(":");
}
