import { useEffect, useState } from "react";

import type {
  AddressingReport,
  AddressingWarning,
  MemoryRegion,
  RangeMapping,
  TranslatedAddressRange,
} from "../models/addressing";
import type { DeviceTreeNode } from "../models/devicetree";
import { AddressSpaceMap } from "./AddressSpaceMap";
import { AddressingIcon, WarningIcon } from "./icons";
import { TranslationTrace } from "./TranslationTrace";

export type AddressingPanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; report: AddressingReport }
  | { status: "error"; message: string; detail: string[] };

interface AddressingPanelProps {
  node: DeviceTreeNode | null;
  state: AddressingPanelState;
  onSelectNodePath?: (nodePath: string) => void;
}

export function AddressingPanel({
  node,
  state,
  onSelectNodePath,
}: AddressingPanelProps) {
  if (!node) {
    return (
      <div className="addressing-empty">
        <AddressingIcon className="empty-icon" />
        <span>Select a node to inspect addressing.</span>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <section className="addressing-section" aria-live="polite">
        <p className="addressing-empty-text">Loading addressing data...</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="addressing-section addressing-error" aria-live="polite">
        <h3>Unable to load addressing data</h3>
        <p>{state.message}</p>
        {state.detail.length > 0 && (
          <ul>
            {state.detail.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </section>
    );
  }

  if (state.status !== "success") {
    return (
      <section className="addressing-section">
        <p className="addressing-empty-text">No addressing data loaded.</p>
      </section>
    );
  }

  const details = selectNodeAddressing(state.report, node.path);
  const hasAddressing =
    details.regions.length > 0 ||
    details.translations.length > 0 ||
    details.mappings.length > 0 ||
    details.warnings.length > 0;
  const hasAddressSpace = state.report.regions.length > 0;

  if (!hasAddressing && !hasAddressSpace) {
    return (
      <section className="addressing-section">
        <p className="addressing-empty-text">
          No address resources described for this node.
        </p>
      </section>
    );
  }

  return (
    <div className="addressing-panel-body">
      {hasAddressSpace && (
        <section
          className="addressing-section"
          aria-labelledby="address-space-heading"
        >
          <SectionHeading id="address-space-heading" title="Address Space" />
          <AddressSpaceMap
            regions={state.report.regions}
            selectedNodePath={node.path}
            onSelectRegion={onSelectNodePath}
          />
        </section>
      )}

      {!hasAddressing && (
        <section className="addressing-section">
          <p className="addressing-empty-text">
            No address resources described for this node.
          </p>
        </section>
      )}

      {details.regions.length > 0 && (
        <section className="addressing-section" aria-labelledby="regions-heading">
          <SectionHeading id="regions-heading" title="Region" />
          <ul className="addressing-list">
            {details.regions.map((region, index) => (
              <MemoryRegionItem
                key={`${region.node_path}:${region.start}:${index}`}
                region={region}
                index={index}
              />
            ))}
          </ul>
        </section>
      )}

      {details.translations.length > 0 && (
        <section className="addressing-section" aria-labelledby="translations-heading">
          <SectionHeading id="translations-heading" title="Translation" />
          <TranslationSection translations={details.translations} />
        </section>
      )}

      {details.mappings.length > 0 && (
        <section className="addressing-section" aria-labelledby="mappings-heading">
          <SectionHeading id="mappings-heading" title="Mapping" />
          <ul className="addressing-list">
            {details.mappings.map((mapping) => (
              <RangeMappingItem
                key={`${mapping.node_path}:${mapping.index}`}
                mapping={mapping}
              />
            ))}
          </ul>
        </section>
      )}

      {details.warnings.length > 0 && (
        <section className="addressing-section" aria-labelledby="warnings-heading">
          <SectionHeading id="warnings-heading" title="Warnings" />
          <ul className="addressing-warning-list">
            {details.warnings.map((warning) => (
              <WarningItem
                key={`${warning.code}:${warning.node_path}:${warning.message}`}
                warning={warning}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function selectNodeAddressing(report: AddressingReport, nodePath: string) {
  const translations = report.translations.filter(
    (translation) => translation.node_path === nodePath,
  );
  const reportWarnings = report.warnings.filter(
    (warning) => warning.node_path === nodePath,
  );
  const translationWarnings = translations.flatMap(
    (translation) => translation.warnings,
  );

  return {
    regions: report.regions.filter((region) => region.node_path === nodePath),
    translations,
    mappings: report.mappings.filter((mapping) => mapping.node_path === nodePath),
    warnings: deduplicateWarnings([...reportWarnings, ...translationWarnings]),
  };
}

interface SectionHeadingProps {
  id: string;
  title: string;
}

function SectionHeading({ id, title }: SectionHeadingProps) {
  return (
    <div className="addressing-section-heading">
      <AddressingIcon className="panel-icon" />
      <h3 id={id}>{title}</h3>
    </div>
  );
}

interface MemoryRegionItemProps {
  region: MemoryRegion;
  index: number;
}

function MemoryRegionItem({ region, index }: MemoryRegionItemProps) {
  return (
    <li className="addressing-card">
      <div className="addressing-card-header">
        <span>Region {index}</span>
        <span className={`region-kind region-kind-${region.kind}`}>
          {region.kind}
        </span>
      </div>
      <AddressingFields
        fields={[
          ["Start", region.start],
          ["Size", region.size],
          ["End", region.end],
        ]}
      />
    </li>
  );
}

interface TranslationSectionProps {
  translations: TranslatedAddressRange[];
}

function TranslationSection({ translations }: TranslationSectionProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const activeIndex = Math.min(selectedIndex, translations.length - 1);
  const activeTranslation = translations[activeIndex];

  useEffect(() => {
    setSelectedIndex(0);
  }, [translations]);

  if (!activeTranslation) {
    return null;
  }

  return (
    <div className="translation-resource-view">
      {translations.length > 1 && (
        <div
          className="translation-resource-tabs"
          role="tablist"
          aria-label="Address resources"
        >
          {translations.map((translation, index) => (
            <button
              className={
                activeIndex === index
                  ? "translation-resource-tab translation-resource-tab-active"
                  : "translation-resource-tab"
              }
              key={`${translation.node_path}:${translation.bus_address}:${index}`}
              type="button"
              role="tab"
              aria-selected={activeIndex === index}
              onClick={() => setSelectedIndex(index)}
            >
              Resource {index}
            </button>
          ))}
        </div>
      )}
      <TranslationResourceCard
        translation={activeTranslation}
        index={activeIndex}
      />
    </div>
  );
}

interface TranslationResourceCardProps {
  translation: TranslatedAddressRange;
  index: number;
}

function TranslationResourceCard({
  translation,
  index,
}: TranslationResourceCardProps) {
  return (
    <div className="translation-card">
      <div className="addressing-card-header">
        <span>Resource {index}</span>
        <span
          className={
            translation.cpu_address === null
              ? "translation-status translation-status-unresolved"
              : "translation-status translation-status-resolved"
          }
        >
          {translation.cpu_address === null ? "unresolved" : "resolved"}
        </span>
      </div>
      <AddressingFields
        fields={[
          ["Bus address", translation.bus_address],
          ["CPU address", translation.cpu_address],
          ["Size", translation.size],
          ["End", translation.end],
        ]}
      />
      <TranslationTrace translation={translation} />
    </div>
  );
}

interface RangeMappingItemProps {
  mapping: RangeMapping;
}

function RangeMappingItem({ mapping }: RangeMappingItemProps) {
  return (
    <li className="addressing-card">
      <div className="addressing-card-header">
        <span>ranges[{mapping.index}]</span>
      </div>
      <AddressingFields
        fields={[
          ["Child address", mapping.child_address],
          ["Parent address", mapping.parent_address],
          ["Size", mapping.size],
        ]}
      />
    </li>
  );
}

interface AddressingFieldsProps {
  fields: Array<[label: string, value: string | null]>;
}

function AddressingFields({ fields }: AddressingFieldsProps) {
  return (
    <dl className="addressing-fields">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <code>{value ?? "-"}</code>
          </dd>
        </div>
      ))}
    </dl>
  );
}

interface WarningItemProps {
  warning: AddressingWarning;
}

function WarningItem({ warning }: WarningItemProps) {
  return (
    <li className="addressing-warning">
      <WarningIcon className="warning-icon" />
      <div>
        <code>{warning.code}</code>
        <p>{warning.message}</p>
      </div>
    </li>
  );
}

function deduplicateWarnings(
  warnings: AddressingWarning[],
): AddressingWarning[] {
  const seen = new Set<string>();
  const result: AddressingWarning[] = [];

  for (const warning of warnings) {
    const key = `${warning.code}\0${warning.node_path}\0${warning.message}`;
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    result.push(warning);
  }

  return result;
}
