import { useEffect, useMemo, useState } from "react";

import { ApiError, getRuntimeInterrupts } from "../api/runtime";
import type {
  RuntimeInterrupt,
  RuntimeInterruptsResponse,
  RuntimeWarning,
} from "../models/runtime";
import { formatHex } from "../models/runtime";
import { RuntimeIcon, SearchIcon, WarningIcon, XIcon } from "./icons";

type RuntimeInterruptState =
  | { status: "loading" }
  | { status: "success"; response: RuntimeInterruptsResponse }
  | { status: "error"; message: string; detail: string[] };

const emptyInterrupts: RuntimeInterrupt[] = [];

interface RuntimeInterruptListProps {
  refreshToken?: number;
}

export function RuntimeInterruptList({
  refreshToken = 0,
}: RuntimeInterruptListProps) {
  const [state, setState] = useState<RuntimeInterruptState>({
    status: "loading",
  });
  const [query, setQuery] = useState("");

  useEffect(() => {
    let isMounted = true;
    setState({ status: "loading" });

    void getRuntimeInterrupts().then(
      (response) => {
        if (isMounted) {
          setState({ status: "success", response });
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

  const interrupts =
    state.status === "success" ? state.response.data : emptyInterrupts;
  const warnings = state.status === "success" ? state.response.warnings : [];
  const trimmedQuery = query.trim();
  const filteredInterrupts = useMemo(
    () => filterInterrupts(interrupts, trimmedQuery),
    [interrupts, trimmedQuery],
  );

  return (
    <section className="runtime-interrupt-list" aria-label="Runtime interrupts">
      <div className="runtime-interrupt-header">
        <div className="panel-title">
          <RuntimeIcon className="panel-icon" />
          <h2>Runtime Interrupts</h2>
        </div>
        {state.status === "success" && (
          <span>{interrupts.length.toLocaleString()} IRQs</span>
        )}
      </div>

      {state.status === "loading" && (
        <div className="runtime-browser-status" aria-live="polite">
          Loading runtime interrupts...
        </div>
      )}

      {state.status === "error" && (
        <div
          className="runtime-browser-status runtime-browser-error"
          aria-live="polite"
        >
          <h3>Unable to load runtime interrupts</h3>
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
          {warnings.length > 0 && <RuntimeInterruptWarnings warnings={warnings} />}
          <div className="runtime-interrupt-toolbar">
            <div className="runtime-search-shell">
              <SearchIcon className="runtime-search-icon" />
              <input
                aria-label="Search runtime interrupts"
                className="runtime-search-input"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search IRQ, controller, action..."
              />
              {query.length > 0 && (
                <button
                  className="runtime-search-clear-button"
                  type="button"
                  aria-label="Clear runtime interrupt search"
                  title="Clear search"
                  onClick={() => setQuery("")}
                >
                  <XIcon className="search-clear-icon" />
                </button>
              )}
            </div>
          </div>

          {interrupts.length === 0 ? (
            <p className="runtime-empty">
              No runtime interrupts reported by the current source.
            </p>
          ) : filteredInterrupts.length === 0 ? (
            <p className="runtime-empty">No matching runtime interrupts.</p>
          ) : (
            <ul
              className="runtime-interrupt-items"
              aria-label="Runtime interrupt list"
            >
              {filteredInterrupts.map((interrupt) => (
                <li key={interrupt.irq}>
                  <RuntimeInterruptItem interrupt={interrupt} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

interface RuntimeInterruptWarningsProps {
  warnings: RuntimeWarning[];
}

function RuntimeInterruptWarnings({ warnings }: RuntimeInterruptWarningsProps) {
  return (
    <ul className="runtime-warning-list" aria-label="Runtime interrupt warnings">
      {warnings.map((warning) => (
        <li key={`${warning.code}:${warning.source_path ?? warning.message}`}>
          <WarningIcon className="warning-icon" />
          <div>
            <strong>{warning.code}</strong>
            <p>{warning.message}</p>
            {warning.source_path && <code>{warning.source_path}</code>}
          </div>
        </li>
      ))}
    </ul>
  );
}

interface RuntimeInterruptItemProps {
  interrupt: RuntimeInterrupt;
}

function RuntimeInterruptItem({ interrupt }: RuntimeInterruptItemProps) {
  return (
    <article className="runtime-interrupt-item">
      <div className="runtime-interrupt-item-header">
        <strong>IRQ {interrupt.irq}</strong>
        <span>{interrupt.total_count.toLocaleString()} total</span>
      </div>
      <dl className="runtime-interrupt-grid">
        <RuntimeInterruptField
          label="Controller"
          value={interrupt.controller}
        />
        <RuntimeInterruptField
          label="HWIRQ"
          value={formatNullableAddress(interrupt.hardware_irq)}
        />
        <RuntimeInterruptField label="Trigger" value={interrupt.trigger} />
        <RuntimeInterruptField
          label="Actions"
          value={formatList(interrupt.actions)}
        />
        <RuntimeInterruptField
          label="Counts"
          value={interrupt.counts.join(" / ")}
        />
        <RuntimeInterruptField label="Source" value={interrupt.source_path} />
      </dl>
    </article>
  );
}

interface RuntimeInterruptFieldProps {
  label: string;
  value: string | null;
}

function RuntimeInterruptField({ label, value }: RuntimeInterruptFieldProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "-"}</code>
      </dd>
    </div>
  );
}

function filterInterrupts(
  interrupts: RuntimeInterrupt[],
  query: string,
): RuntimeInterrupt[] {
  if (!query) {
    return interrupts;
  }

  const needle = query.toLowerCase();
  return interrupts.filter((interrupt) =>
    [
      interrupt.irq.toString(),
      interrupt.controller,
      interrupt.hardware_irq?.toString(),
      interrupt.trigger,
      ...interrupt.actions,
      interrupt.raw_line,
      interrupt.source_path,
    ].some((value) => value?.toLowerCase().includes(needle)),
  );
}

function formatNullableAddress(value: number | null): string | null {
  return value === null ? null : `${value.toString()} (${formatHex(value)})`;
}

function formatList(values: string[]): string | null {
  return values.length === 0 ? null : values.join(", ");
}

function toErrorState(error: unknown): RuntimeInterruptState {
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
