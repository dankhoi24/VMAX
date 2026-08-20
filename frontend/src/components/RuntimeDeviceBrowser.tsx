import { useEffect, useMemo, useState } from "react";

import { ApiError, getRuntimeDevices } from "../api/runtime";
import type {
  RuntimeDevice,
  RuntimeDevicesResponse,
  RuntimeWarning,
} from "../models/runtime";
import { RuntimeIcon, SearchIcon, WarningIcon, XIcon } from "./icons";

type RuntimeDeviceState =
  | { status: "loading" }
  | { status: "success"; response: RuntimeDevicesResponse }
  | { status: "error"; message: string; detail: string[] };

type BindingState = "bound" | "unbound" | "unknown";

const driverBindingReadFailedCode = "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED";
const emptyDevices: RuntimeDevice[] = [];

export function RuntimeDeviceBrowser() {
  const [state, setState] = useState<RuntimeDeviceState>({
    status: "loading",
  });
  const [query, setQuery] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    void getRuntimeDevices().then(
      (response) => {
        if (isMounted) {
          setState({ status: "success", response });
          setSelectedPath(
            (current) => current ?? response.data[0]?.sysfs_path ?? null,
          );
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

  const devices =
    state.status === "success" ? state.response.data : emptyDevices;
  const warnings =
    state.status === "success" ? state.response.warnings : [];
  const trimmedQuery = query.trim();
  const filteredDevices = useMemo(
    () => filterDevices(devices, trimmedQuery),
    [devices, trimmedQuery],
  );
  const selectedDevice =
    filteredDevices.find((device) => device.sysfs_path === selectedPath) ?? null;

  useEffect(() => {
    if (state.status !== "success") {
      return;
    }

    const nextSelectedPath = filteredDevices[0]?.sysfs_path ?? null;
    if (
      selectedPath !== null &&
      filteredDevices.some((device) => device.sysfs_path === selectedPath)
    ) {
      return;
    }

    if (selectedPath !== nextSelectedPath) {
      setSelectedPath(nextSelectedPath);
    }
  }, [filteredDevices, selectedPath, state.status]);

  return (
    <section className="runtime-browser" aria-label="Runtime devices">
      <div className="runtime-browser-header">
        <div className="panel-title">
          <RuntimeIcon className="panel-icon" />
          <h2>Runtime Devices</h2>
        </div>
        {state.status === "success" && (
          <span>{devices.length.toLocaleString()} devices</span>
        )}
      </div>

      {state.status === "loading" && (
        <div className="runtime-browser-status" aria-live="polite">
          Loading runtime devices...
        </div>
      )}

      {state.status === "error" && (
        <div
          className="runtime-browser-status runtime-browser-error"
          aria-live="polite"
        >
          <h3>Unable to load runtime devices</h3>
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
          {warnings.length > 0 && <RuntimeWarnings warnings={warnings} />}
          <div className="runtime-browser-body">
            <div className="runtime-device-list-panel">
              <div className="runtime-search-shell">
                <SearchIcon className="runtime-search-icon" />
                <input
                  aria-label="Search runtime devices"
                  className="runtime-search-input"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search runtime devices..."
                />
                {query.length > 0 && (
                  <button
                    className="runtime-search-clear-button"
                    type="button"
                    aria-label="Clear runtime device search"
                    title="Clear search"
                    onClick={() => setQuery("")}
                  >
                    <XIcon className="search-clear-icon" />
                  </button>
                )}
              </div>

              {devices.length === 0 ? (
                <p className="runtime-empty">No runtime devices found.</p>
              ) : filteredDevices.length === 0 ? (
                <p className="runtime-empty">No matching runtime devices.</p>
              ) : (
                <ul className="runtime-device-list" aria-label="Runtime device list">
                  {filteredDevices.map((device) => (
                    <li key={device.sysfs_path}>
                      <button
                        className={getDeviceButtonClassName(
                          selectedPath === device.sysfs_path,
                        )}
                        type="button"
                        aria-pressed={selectedPath === device.sysfs_path}
                        onClick={() => setSelectedPath(device.sysfs_path)}
                      >
                        <span className="runtime-device-row-main">
                          <span className="runtime-device-name">
                            {device.name}
                          </span>
                          <BindingBadge device={device} warnings={warnings} />
                        </span>
                        <span className="runtime-device-row-meta">
                          {device.driver_name ?? device.bus}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <RuntimeDeviceDetails device={selectedDevice} warnings={warnings} />
          </div>
        </>
      )}
    </section>
  );
}

interface RuntimeWarningsProps {
  warnings: RuntimeWarning[];
}

function RuntimeWarnings({ warnings }: RuntimeWarningsProps) {
  return (
    <ul className="runtime-warning-list" aria-label="Runtime warnings">
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

interface RuntimeDeviceDetailsProps {
  device: RuntimeDevice | null;
  warnings: RuntimeWarning[];
}

function RuntimeDeviceDetails({ device, warnings }: RuntimeDeviceDetailsProps) {
  if (!device) {
    return (
      <aside className="runtime-device-detail" aria-label="Runtime device detail">
        <div className="runtime-detail-empty">Select a runtime device.</div>
      </aside>
    );
  }

  return (
    <aside className="runtime-device-detail" aria-label="Runtime device detail">
      <div className="runtime-detail-heading">
        <code>{device.name}</code>
        <BindingBadge device={device} warnings={warnings} />
      </div>
      <dl className="runtime-detail-grid">
        <RuntimeField label="sysfs_path" value={device.sysfs_path} />
        <RuntimeField label="bus" value={device.bus} />
        <RuntimeField label="driver_name" value={device.driver_name} />
        <RuntimeField label="driver_path" value={device.driver_path} />
        <RuntimeField
          label="of_node_sysfs_path"
          value={device.of_node_sysfs_path}
        />
        <RuntimeField label="modalias" value={device.modalias} />
        <RuntimeField
          label="resources"
          value={formatResourceCount(device.resources.length)}
        />
      </dl>
    </aside>
  );
}

interface RuntimeFieldProps {
  label: string;
  value: string | null;
}

function RuntimeField({ label, value }: RuntimeFieldProps) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <code>{value ?? "-"}</code>
      </dd>
    </div>
  );
}

interface BindingBadgeProps {
  device: RuntimeDevice;
  warnings: RuntimeWarning[];
}

function BindingBadge({ device, warnings }: BindingBadgeProps) {
  const bindingState = getBindingState(device, warnings);

  return (
    <span className={getBindingBadgeClassName(bindingState)}>
      {bindingState}
    </span>
  );
}

function getBindingState(
  device: RuntimeDevice,
  warnings: RuntimeWarning[],
): BindingState {
  if (device.driver_name !== null) {
    return "bound";
  }

  const driverPath = `${device.sysfs_path}/driver`;
  const bindingUnknown = warnings.some(
    (warning) =>
      warning.code === driverBindingReadFailedCode &&
      warning.source_path === driverPath,
  );

  return bindingUnknown ? "unknown" : "unbound";
}

function filterDevices(
  devices: RuntimeDevice[],
  query: string,
): RuntimeDevice[] {
  if (!query) {
    return devices;
  }

  const needle = query.toLowerCase();
  return devices.filter((device) =>
    [
      device.name,
      device.sysfs_path,
      device.bus,
      device.driver_name,
      device.driver_path,
      device.of_node_sysfs_path,
      device.modalias,
    ].some((value) => value?.toLowerCase().includes(needle)),
  );
}

function formatResourceCount(count: number): string {
  return count === 1 ? "1 resource" : `${count.toLocaleString()} resources`;
}

function getDeviceButtonClassName(isSelected: boolean): string {
  return isSelected
    ? "runtime-device-button runtime-device-button-selected"
    : "runtime-device-button";
}

function getBindingBadgeClassName(bindingState: BindingState): string {
  if (bindingState === "bound") {
    return "runtime-badge runtime-badge-bound";
  }

  if (bindingState === "unknown") {
    return "runtime-badge runtime-badge-unknown";
  }

  return "runtime-badge";
}

function toErrorState(error: unknown): RuntimeDeviceState {
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
