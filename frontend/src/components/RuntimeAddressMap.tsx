import { useEffect, useState } from "react";

import { ApiError, getRuntimeIomem } from "../api/runtime";
import type {
  IomemRegion,
  RuntimeIomemResponse,
  RuntimeWarning,
} from "../models/runtime";
import { formatHex } from "../models/runtime";
import { AddressingIcon, WarningIcon } from "./icons";

type RuntimeIomemState =
  | { status: "loading" }
  | { status: "success"; response: RuntimeIomemResponse }
  | { status: "error"; message: string; detail: string[] };

const redactedIomemCode = "PROC_IOMEM_ADDRESSES_REDACTED";

export function RuntimeAddressMap() {
  const [state, setState] = useState<RuntimeIomemState>({
    status: "loading",
  });

  useEffect(() => {
    let isMounted = true;

    void getRuntimeIomem().then(
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
  }, []);

  const regions = state.status === "success" ? state.response.data : [];
  const warnings = state.status === "success" ? state.response.warnings : [];
  const isRedacted = warnings.some(
    (warning) => warning.code === redactedIomemCode,
  );

  return (
    <section className="runtime-address-map" aria-label="Runtime address map">
      <div className="runtime-address-map-header">
        <div className="panel-title">
          <AddressingIcon className="panel-icon" />
          <h2>Runtime Address Map</h2>
        </div>
        {state.status === "success" && (
          <span>{regions.length.toLocaleString()} root regions</span>
        )}
      </div>

      {state.status === "loading" && (
        <div className="runtime-browser-status" aria-live="polite">
          Loading runtime address map...
        </div>
      )}

      {state.status === "error" && (
        <div
          className="runtime-browser-status runtime-browser-error"
          aria-live="polite"
        >
          <h3>Unable to load runtime address map</h3>
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
          {warnings.length > 0 && <RuntimeIomemWarnings warnings={warnings} />}
          {isRedacted ? (
            <div className="runtime-iomem-unavailable" aria-live="polite">
              <strong>Runtime address information is unavailable.</strong>
              <p>The kernel is hiding /proc/iomem addresses.</p>
            </div>
          ) : regions.length === 0 ? (
            <p className="runtime-iomem-empty">
              No runtime address regions reported by the current source.
            </p>
          ) : (
            <RuntimeIomemTree regions={regions} />
          )}
        </>
      )}
    </section>
  );
}

interface RuntimeIomemWarningsProps {
  warnings: RuntimeWarning[];
}

function RuntimeIomemWarnings({ warnings }: RuntimeIomemWarningsProps) {
  return (
    <ul className="runtime-warning-list" aria-label="Runtime iomem warnings">
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

interface RuntimeIomemTreeProps {
  regions: IomemRegion[];
}

function RuntimeIomemTree({ regions }: RuntimeIomemTreeProps) {
  return (
    <ul className="runtime-iomem-tree" aria-label="Runtime iomem hierarchy">
      {regions.map((region) => (
        <RuntimeIomemRegion key={getRegionKey(region)} region={region} depth={0} />
      ))}
    </ul>
  );
}

interface RuntimeIomemRegionProps {
  region: IomemRegion;
  depth: number;
}

function RuntimeIomemRegion({ region, depth }: RuntimeIomemRegionProps) {
  return (
    <li className="runtime-iomem-region-item">
      <article
        className="runtime-iomem-region"
        aria-label={`Runtime region ${region.name}`}
        style={{ marginLeft: depth === 0 ? 0 : 18 }}
      >
        <div className="runtime-iomem-region-main">
          <strong>{region.name}</strong>
          {region.children.length > 0 && (
            <span className="runtime-iomem-child-count">
              {region.children.length.toLocaleString()} children
            </span>
          )}
        </div>
        <div className="runtime-iomem-range">
          <code>{formatHex(region.start)}</code>
          <span>-</span>
          <code>{formatHex(region.end)}</code>
        </div>
        <dl className="runtime-iomem-fields">
          <div>
            <dt>Size</dt>
            <dd>
              <code>{formatHex(region.size)}</code>
            </dd>
          </div>
        </dl>
      </article>
      {region.children.length > 0 && (
        <ul className="runtime-iomem-tree runtime-iomem-tree-children">
          {region.children.map((child) => (
            <RuntimeIomemRegion
              key={getRegionKey(child)}
              region={child}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function getRegionKey(region: IomemRegion): string {
  return `${region.start}:${region.end}:${region.name}`;
}

function toErrorState(error: unknown): RuntimeIomemState {
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
