import { useMemo, useState } from "react";

import type { DeviceTreeNode } from "../models/devicetree";
import {
  searchDeviceTree,
  type DeviceTreeSearchResult,
} from "../search/devicetreeSearch";

interface SearchBoxProps {
  root: DeviceTreeNode;
  onSelectResult: (node: DeviceTreeNode) => void;
}

export function SearchBox({ root, onSelectResult }: SearchBoxProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => searchDeviceTree(root, query), [root, query]);
  const hasQuery = query.trim().length > 0;

  return (
    <section className="search-panel" aria-label="Device Tree search">
      <div className="search-header">
        <h2>Search</h2>
        {hasQuery && (
          <span>
            {results.length.toLocaleString()}{" "}
            {results.length === 1 ? "match" : "matches"}
          </span>
        )}
      </div>
      <input
        className="search-input"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Search Device Tree"
        placeholder="Search"
      />

      {hasQuery && results.length === 0 && (
        <p className="search-empty">No matches</p>
      )}

      {results.length > 0 && (
        <ul className="search-results">
          {results.map((result) => (
            <SearchResultItem
              key={result.node.path}
              result={result}
              onSelectResult={onSelectResult}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

interface SearchResultItemProps {
  result: DeviceTreeSearchResult;
  onSelectResult: (node: DeviceTreeNode) => void;
}

function SearchResultItem({ result, onSelectResult }: SearchResultItemProps) {
  return (
    <li>
      <button
        className="search-result-button"
        type="button"
        onClick={() => onSelectResult(result.node)}
      >
        <span className="search-result-name">{result.node.full_name}</span>
        <span className="search-result-path">{result.node.path}</span>
        <span className="search-match-list" aria-label="Matched fields">
          {result.matches.map((match) => (
            <span className="search-match" key={match}>
              {match}
            </span>
          ))}
        </span>
      </button>
    </li>
  );
}
