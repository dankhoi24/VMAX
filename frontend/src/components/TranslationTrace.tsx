import type {
  TranslatedAddressRange,
  TranslationStep,
} from "../models/addressing";
import { AddressingIcon, WarningIcon } from "./icons";

interface TranslationTraceProps {
  translation: TranslatedAddressRange;
}

export function TranslationTrace({ translation }: TranslationTraceProps) {
  const isResolved = translation.cpu_address !== null;

  return (
    <div className="translation-trace" aria-label="Address translation trace">
      <TraceEndpoint
        label="Bus address"
        value={translation.bus_address}
        variant="source"
      />

      {translation.translation_path.map((step, index) => (
        <TraceStep
          key={`${step.bus_node_path}:${step.input_address}:${index}`}
          step={step}
          index={index}
        />
      ))}

      {translation.translation_path.length === 0 && isResolved && (
        <TraceDirectNote />
      )}

      <TraceEndpoint
        label={isResolved ? "CPU address" : "Unresolved"}
        value={translation.cpu_address ?? "-"}
        variant={isResolved ? "target" : "unresolved"}
      />
    </div>
  );
}

interface TraceEndpointProps {
  label: string;
  value: string;
  variant: "source" | "target" | "unresolved";
}

function TraceEndpoint({ label, value, variant }: TraceEndpointProps) {
  const className = `trace-endpoint trace-endpoint-${variant}`;

  return (
    <div className={className}>
      {variant === "unresolved" ? (
        <WarningIcon className="trace-endpoint-icon" />
      ) : (
        <AddressingIcon className="trace-endpoint-icon" />
      )}
      <span>{label}</span>
      <code>{value}</code>
    </div>
  );
}

interface TraceStepProps {
  step: TranslationStep;
  index: number;
}

function TraceStep({ step, index }: TraceStepProps) {
  const mappingLabel =
    step.mapping_index === null ? "identity" : `ranges[${step.mapping_index}]`;

  return (
    <div className="trace-step">
      <div className="trace-rail" aria-hidden="true">
        <span>{index + 1}</span>
      </div>
      <div className="trace-step-card">
        <div className="trace-step-header">
          <code>{step.bus_node_path}</code>
          <span
            className={
              step.mapping_index === null
                ? "trace-mapping trace-mapping-identity"
                : "trace-mapping"
            }
          >
            {mappingLabel}
          </span>
        </div>
        <div className="trace-address-pair">
          <code>{step.input_address}</code>
          <span aria-hidden="true">-&gt;</span>
          <code>{step.output_address}</code>
        </div>
      </div>
    </div>
  );
}

function TraceDirectNote() {
  return (
    <div className="trace-direct" aria-label="No address translation required">
      <div className="trace-direct-rail" aria-hidden="true" />
      <span>No address translation required</span>
    </div>
  );
}
