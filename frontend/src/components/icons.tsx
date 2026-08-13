interface IconProps {
  className?: string;
}

export function AddressingIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 12h14" />
      <path d="m15 8 4 4-4 4" />
      <path d="M5 6h4" />
      <path d="M5 18h4" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="m5 12 5 5L20 7" />
    </svg>
  );
}

export function CopyIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <rect x="9" y="9" width="10" height="10" rx="2" />
      <path d="M5 15V7a2 2 0 0 1 2-2h8" />
    </svg>
  );
}

export function NodeIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3 5 7v10l7 4 7-4V7l-7-4Z" />
      <path d="m5 7 7 4 7-4" />
      <path d="M12 11v10" />
    </svg>
  );
}

export function PropertiesIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M6 4h12v16H6z" />
      <path d="M9 8h6" />
      <path d="M9 12h6" />
      <path d="M9 16h4" />
    </svg>
  );
}

export function RefreshIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M20 12a8 8 0 1 1-2.34-5.66" />
      <path d="M20 4v6h-6" />
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="7" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

export function TreeIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 4v6" />
      <path d="M6 14v6" />
      <path d="M18 14v6" />
      <path d="M6 14h12" />
      <path d="M12 10h6v4" />
      <path d="M12 10H6v4" />
    </svg>
  );
}

export function WarningIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3 2 20h20L12 3Z" />
      <path d="M12 9v5" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function XIcon({ className }: IconProps) {
  return (
    <svg className={className} aria-hidden="true" viewBox="0 0 24 24">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}
