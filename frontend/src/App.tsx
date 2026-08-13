import { useCallback, useEffect, useState } from "react";

import { getAddressingReport } from "./api/addressing";
import { ApiError, getDeviceTree } from "./api/devicetree";
import { DeviceTreeView } from "./components/DeviceTreeView";
import { RefreshIcon } from "./components/icons";
import { PropertyPanel } from "./components/PropertyPanel";
import { SearchBox } from "./components/SearchBox";
import type { AddressingReport } from "./models/addressing";
import type { DeviceTreeNode, DeviceTreeResponse } from "./models/devicetree";
import { getAncestorPaths } from "./search/devicetreeSearch";

type LoadState =
  | { status: "loading" }
  | { status: "success"; tree: DeviceTreeResponse }
  | { status: "error"; message: string; detail: string[] };

type AddressingLoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; report: AddressingReport }
  | { status: "error"; message: string; detail: string[] };

export function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [addressingState, setAddressingState] = useState<AddressingLoadState>({
    status: "idle",
  });
  const [selectedNode, setSelectedNode] = useState<DeviceTreeNode | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [selectionRequest, setSelectionRequest] = useState(0);

  const selectNode = useCallback((node: DeviceTreeNode) => {
    setSelectedNode(node);
    setSelectionRequest((current) => current + 1);
    setExpandedPaths((current) => {
      const next = new Set(current);
      getAncestorPaths(node.path).forEach((path) => next.add(path));
      return next;
    });
  }, []);

  const toggleNode = useCallback((path: string) => {
    setExpandedPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const loadTree = useCallback(async () => {
    setState({ status: "loading" });
    setAddressingState({ status: "loading" });
    setSelectedNode(null);
    setExpandedPaths(new Set());
    setSelectionRequest(0);

    const [treeResult, addressingResult] = await Promise.allSettled([
      getDeviceTree(),
      getAddressingReport(),
    ]);

    if (treeResult.status === "fulfilled") {
      const tree = treeResult.value;
      setState({ status: "success", tree });
      setSelectedNode(tree.root);
      setExpandedPaths(new Set([tree.root.path]));
      setSelectionRequest(1);
    } else {
      setState(toErrorState(treeResult.reason));
      setAddressingState({ status: "idle" });
      setSelectedNode(null);
      setExpandedPaths(new Set());
      setSelectionRequest(0);
      return;
    }

    if (addressingResult.status === "fulfilled") {
      setAddressingState({
        status: "success",
        report: addressingResult.value,
      });
    } else {
      setAddressingState(toAddressingErrorState(addressingResult.reason));
    }
  }, []);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <h1>VMAX</h1>
          <span>Device Tree Explorer</span>
        </div>
        <button className="reload-button" type="button" onClick={loadTree}>
          <RefreshIcon className="button-icon" />
          Reload
        </button>
      </header>

      {state.status === "success" && (
        <SearchBox root={state.tree.root} onSelectResult={selectNode} />
      )}

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
        <div className="workspace-grid">
          <DeviceTreeView
            root={state.tree.root}
            nodeCount={state.tree.node_count}
            expandedPaths={expandedPaths}
            selectedPath={selectedNode?.path ?? null}
            selectionRequest={selectionRequest}
            onToggleNode={toggleNode}
            onSelectNode={selectNode}
          />
          <PropertyPanel
            node={selectedNode}
            addressingState={addressingState}
          />
        </div>
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

function toAddressingErrorState(error: unknown): AddressingLoadState {
  const errorState = toErrorState(error);
  if (errorState.status !== "error") {
    return {
      status: "error",
      message: "Unknown error",
      detail: [],
    };
  }

  return {
    status: "error",
    message: errorState.message,
    detail: errorState.detail,
  };
}
