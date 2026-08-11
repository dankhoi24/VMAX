# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and is designed to grow toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, kernel symbols, snapshots, and SoC-specific plugins.

> Status: early development. The current V0.1 work focuses on a reliable, generic Device Tree core.

## Why VMAX

Low-level Linux and embedded debugging often requires jumping between multiple views of the same hardware:

- Device Tree source / DTB
- `/sys` and `/proc`
- driver bindings
- MMIO and reserved memory
- IRQ routing
- DMA and IOMMU mappings
- kernel symbols and runtime events

VMAX aims to correlate those views into one consistent model instead of treating them as separate tools and files.

## Current V0.1 scope

The current implementation focuses only on Device Tree parsing and modeling:

```text
.dtb
  |
  v
pylibfdt
  |
  v
LibFdtDeviceTreeParser
  |
  +--> PropertyDecoder
  |
  v
DeviceTree domain model
```

Implemented core pieces:

- `DeviceTree`, `DeviceTreeNode`, `DeviceTreeProperty`, and `ParseResult` domain models
- conservative property decoding for boolean, string, string-list, cell, and unknown values
- direct DTB parsing through `pylibfdt`
- recursive node/property traversal
- preservation of raw property bytes
- unit tests with a fake libfdt adapter
- integration test using a real DTB fixture and real `pylibfdt`

V0.1 intentionally does **not** yet include `/proc`, `/sys`, runtime driver correlation, MMIO interpretation, IRQ runtime data, DMA/IOMMU analysis, WebSocket events, or SoC-specific behavior.

## Architecture direction

```text
Browser (React + TypeScript)
        |
        | REST / WebSocket
        v
FastAPI Backend
        |
        +-------------------------------+
        |                               |
   Providers / Collectors        Correlation Engine
        |                               |
        +---------------+---------------+
                        |
                  Unified Model
                 /      |      \
             Static   Runtime   Events
```

The core is intended to stay platform-agnostic. OS- and SoC-specific support should be added through providers and plugins rather than forks.

Planned layers:

```text
Core
├── Model
├── Correlation Engine
├── Diff Engine
└── Diagnostics Rules
     ▲
Providers / Collectors
├── Linux
├── QNX (later)
└── Static
     ▲
SoC plugins
├── Generic ARM64
├── Raspberry Pi
└── Renesas R-Car
```

## Roadmap

- **V0.1 — Device Tree Explorer**: DTB parsing, domain model, API, tree browser, property panel, search
- **V0.2 — Memory/MMIO Map**: interpret `reg`, `ranges`, reserved memory, and address cells
- **V0.3 — Linux Runtime Explorer**: `/sys`, `/proc`, devices and runtime resources
- **V0.4 — DT ↔ Device ↔ Driver correlation**
- **V0.5 — IRQ and dependency graph**
- **V0.6 — PCIe topology and snapshots**
- **V0.7 — IOMMU/DMA foundation**
- **V0.8 — Live event engine**
- **V0.9 — R-Car/IPMMU plugin**
- **V1.0 — Diff, diagnostics, packaging and tests**

QNX support is planned after the Linux-oriented V1.0 core is stable.

## Repository layout

```text
backend/
├── app/
│   ├── model/
│   │   └── devicetree.py
│   └── parsers/
│       └── devicetree/
│           ├── decoder.py
│           └── libfdt_parser.py
└── tests/
    ├── fixtures/
    ├── test_devicetree_model.py
    ├── test_property_decoder.py
    └── test_libfdt_parser.py
```

The frontend and API layers will be added as V0.1 progresses.

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: ambiguous values remain `UNKNOWN` rather than being misclassified.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: V0.1 decodes representation; later versions interpret `reg`, `ranges`, IRQs, and other hardware meaning.
- **Keep the core generic**: Raspberry Pi and R-Car should use the same parser/model contracts.

## Development

Backend tests are written with Python `unittest`.

```bash
cd backend
python -m unittest discover -s tests
```

The real-DTB integration test runs when the `libfdt` Python binding (`pylibfdt`) is available. Otherwise that specific integration test is skipped while unit tests continue to run.

## Project status

VMAX is currently under active early development. Interfaces, package layout, and roadmap details may still change before the first public release.
