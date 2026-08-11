import { useCallback, useEffect, useState } from "react";

import { ApiError, getDeviceTree } from "./api/devicetree";
import { DeviceTreeView } from "./components/DeviceTreeView";
import type { DeviceTreeResponse } from "./models/devicetree";

type LoadState =
  | { status: "loading" }
  | { status: "success"; tree: DeviceTreeResponse }
  | { status: "error"; message: string; detail: string[] };

export function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  const loadTree = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const tree = await getDeviceTree();
      setState({ status: "success", tree });
    } catch (error) {
      setState(toErrorState(error));
    }
  }, []);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>VMAX</h1>
          <p>Device Tree</p>
        </div>
        <button className="reload-button" type="button" onClick={loadTree}>
          Reload
        </button>
      </header>

      {state.status === "loading" && (
        <section className="status-panel" aria-live="polite">
          Loading Device Tree...
        </section>
      )}

      {state.status === "error" && (
        <section className="status-panel error-panel" aria-live="polite">
          <h2>Unable to load Device Tree</h2>
          <p>{state.message}</p>
          {state.detail.length > 0 && (
            <ul>
              {state.detail.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {state.status === "success" && (
        <DeviceTreeView root={state.tree.root} nodeCount={state.tree.node_count} />
      )}
    </main>
  );
}

function toErrorState(error: unknown): LoadState {
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
