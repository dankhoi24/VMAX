# Changelog

All notable changes to VMAX are documented in this file.

## [0.5.0] - 2026-08-27

### Added

- Device dependency domain for clocks, resets, power domains, DMA, IOMMU, and interrupts.
- Device Tree dependency extraction with provider resolution, named entries, raw specifier preservation, and provenance.
- Explicit and natural `interrupt-parent` handling plus `interrupts-extended` support.
- Linux runtime interrupt collection from `/proc/interrupts` with supplemental IRQ metadata from sysfs/procfs.
- Canonical GIC SPI/PPI hardware IRQ identity translation.
- Conservative DT interrupt ↔ Linux runtime IRQ correlation using controller + HWIRQ identity.
- Explicit `resolved`, `unresolved`, `unavailable`, and `ambiguous` dependency/correlation states.
- `GET /api/v1/runtime/interrupts`.
- `GET /api/v1/dependencies/devices`.
- Runtime Interrupts frontend explorer.
- Device Dependencies frontend explorer with static/runtime status separation, warnings, and ambiguous candidates.
- Interactive dependency focus graph with provider navigation and relationship direction.

### Changed

- Static dependency resolution and runtime IRQ mapping are represented as separate semantics.
- Runtime-source failures preserve usable static dependency topology rather than failing the whole dependency view.
- Dependency graph copy now distinguishes static `consumer -> provider` relationships from `provider -> IRQ` runtime mapping.

### Validation

- Frontend: 21 test files, 125 tests passed.
- TypeScript typecheck passed.
- Production frontend build passed.
- UI validation passed.
- Existing backend regression coverage retained for dependency extraction, IRQ correlation, API serialization, and partial-source behavior.

## [0.4.0]

- Added explicit DT ↔ Linux runtime-device correlation, driver association, and `/proc/iomem` physical-resource correlation.

## [0.3.0]

- Added Linux runtime exploration, local/SSH transport, runtime devices/drivers, and `/proc/iomem` collection.

## [0.2.0]

- Added Device Tree addressing, `reg` / `ranges` interpretation, translation tracing, and address-space visualization.

## [0.1.0]

- Initial Device Tree explorer with parsing, domain model, API, tree browser, property inspection, and search.
