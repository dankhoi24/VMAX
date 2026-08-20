# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and is designed to grow toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, kernel symbols, snapshots, and SoC-specific plugins.

> **v0.2.0 — Memory/MMIO Map:** the second public development release of VMAX, adding semantic Device Tree address analysis, address-translation tracing, and an interactive physical address-space map on top of the v0.1 Device Tree Explorer.

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

## v0.2.0 scope

VMAX v0.2.0 extends the Device Tree exploration path with semantic address analysis:

```text
.dtb
  |
  v
pylibfdt
  |
  v
LibFdtDeviceTreeParser
  |
  v
DeviceTree domain model
  |
  +--> AddressCellContextResolver
  +--> RegInterpreter
  +--> RangesInterpreter / RangesTranslator
  +--> MemoryRegionClassifier
  |
  v
AddressingReport
  |
  v
FastAPI + Pydantic API schema
  |
  | JSON
  v
TypeScript API client
  |
  v
React
  ├── Search
  ├── DeviceTreeView
  ├── PropertyPanel
  ├── AddressingPanel
  ├── TranslationTrace
  └── AddressSpaceMap
```

Implemented in v0.2.0:

- all v0.1.0 Device Tree parsing, browsing, property inspection, and search capabilities
- addressing domain models for cell contexts, `reg` resources, range mappings, translations, memory regions, and structured warnings
- `#address-cells` and `#size-cells` context resolution with provenance
- Device Tree `reg` interpretation, including multiple resources per node
- `ranges` interpretation and child-bus to parent-bus / CPU address translation
- explicit distinction between missing `ranges` and empty identity `ranges`
- translation provenance through `TranslationStep` records
- RAM, reserved-memory, and device-region classification
- conservative handling of unsupported bus address formats without fabricating translations
- 64-bit / greater-than-4-GiB address preservation
- FastAPI addressing endpoint and typed frontend addressing models
- selected-node Addressing panel with exact hexadecimal values
- Translation Trace for bus-to-CPU provenance
- interactive Address Space Map with BigInt-safe address handling
- map support for overlaps, nesting, gaps, clusters, selection, zoom, pan, Fit All, and Fit Selected
- progressive loading so Device Tree browsing remains usable while addressing data resolves
- backend unit/integration coverage plus real Raspberry Pi 5 DTB semantic validation

v0.2.0 intentionally does **not** yet include `/proc`, `/sys`, runtime driver correlation, runtime MMIO ownership, IRQ runtime data, DMA/IOMMU/IOVA mappings, PCI-specific 3-cell address semantics, WebSocket events, or SoC-specific runtime behavior.

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

- **v0.1 — Device Tree Explorer**: DTB parsing, domain model, API, tree browser, property panel, search — **complete**
- **v0.2 — Memory/MMIO Map**: `reg`, `ranges`, address cells, memory regions, translation trace, address-space map — **complete**
- **v0.3 — Linux Runtime Explorer**: `/sys`, `/proc`, devices and runtime resources — **next**
- **v0.4 — DT ↔ Device ↔ Driver correlation**
- **v0.5 — IRQ and dependency graph**
- **v0.6 — PCIe topology and snapshots**
- **v0.7 — IOMMU/DMA foundation**
- **v0.8 — Live event engine**
- **v0.9 — R-Car/IPMMU plugin**
- **v1.0 — Diff, diagnostics, packaging and tests**

QNX support is planned after the Linux-oriented v1.0 core is stable.

## Repository layout

```text
backend/
├── app/
│   ├── addressing/
│   ├── api/
│   ├── collectors/
│   ├── model/
│   ├── parsers/
│   └── services/
└── tests/

frontend/
├── src/
│   ├── api/
│   ├── components/
│   ├── models/
│   ├── search/
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

## Run VMAX

A convenient Windows development setup is:

```text
Windows
└── React / Vite frontend
    └── http://localhost:5173
            |
            | /api proxy
            v
WSL / Ubuntu
└── FastAPI backend
    └── http://localhost:8000
            |
            v
        pylibfdt
            |
            v
           DTB
```

The source repository can remain on the Windows filesystem. For example:

```text
Windows: C:\Users\<USER>\Documents\VMAX
WSL:     /mnt/c/Users/<USER>/Documents/VMAX
```

### 1. Frontend prerequisites on Windows

Install a Node.js LTS release, then verify:

```powershell
node --version
npm --version
```

Install the frontend dependencies from PowerShell:

```powershell
cd C:\Users\<USER>\Documents\VMAX\frontend
npm install
```

Optional validation:

```powershell
npm test
npm run typecheck
npm run build
```

### 2. Backend prerequisites in WSL / Ubuntu

Open WSL and install the native tools required to build `pylibfdt`:

```bash
sudo apt update
sudo apt install -y curl build-essential swig python3-dev
```

Install `uv` with the official standalone installer if it is not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

Because the repository is shared with Windows, keep the Linux Python environment outside the repository so it does not conflict with a Windows `.venv`:

```bash
mkdir -p ~/.venvs
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/vmax-wsl"
```

Change to the same repository through the WSL mount and install the backend dependencies, including the DTB parser extra:

```bash
cd /mnt/c/Users/<USER>/Documents/VMAX
uv sync --extra dev --extra dtb
```

Verify the `libfdt` Python module:

```bash
uv run python -c "import libfdt; print(libfdt.__file__)"
```

### 3. Start the backend in WSL

Select the DTB that VMAX should load:

```bash
export PYTHONPATH=backend
export VMAX_DTB_PATH=/mnt/c/Users/<USER>/Downloads/bcm2712-rpi-5-b.dtb
```

Start FastAPI/Uvicorn:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend should now be available at:

```text
http://localhost:8000
```

Useful endpoints:

```text
GET http://localhost:8000/api/v1/metadata
GET http://localhost:8000/api/v1/devicetree
GET http://localhost:8000/api/v1/addressing
```

### 4. Start the frontend on Windows

In a second terminal:

```powershell
cd C:\Users\<USER>\Documents\VMAX\frontend
npm run dev
```

Vite normally starts the frontend at:

```text
http://localhost:5173
```

Open that URL in a browser. The Vite development server proxies `/api` requests to the FastAPI backend on port `8000`, so no backend URL needs to be hard-coded in the frontend.

### 5. Expected result

With both processes running, the browser provides:

- expandable/collapsible Device Tree navigation
- selected-node property inspection
- decoded property values with optional raw-hex inspection
- local search and navigation to matching nodes
- semantic `reg` / `ranges` address information for selected nodes
- bus-to-CPU Translation Trace
- interactive physical Address Space Map

## Tests

Run backend tests from the repository root in the Python environment:

```bash
export PYTHONPATH=backend
uv run --extra dev --extra dtb python -m unittest discover -s backend/tests -v
```

Run frontend tests, type checking, and the production build from `frontend/`:

```bash
npm test
npm run typecheck
npm run build
```

The real-DTB backend path requires the `libfdt` Python binding (`pylibfdt`).

## Validation

v0.2.0 addressing semantics have been validated with a real Raspberry Pi 5 DTB through the production parser and addressing pipeline.

The real-DTB validation covers:

- exact RAM and fixed reserved-memory regions
- no fabricated static region for dynamic CMA without `reg`
- simple-bus `ranges` translation with exact bus and CPU addresses
- translation provenance
- multiple `reg` resources
- addresses above 4 GiB
- structured handling of unsupported PCI 3-cell address formats

The full frontend regression suite, TypeScript type check, production build, and backend regression suite are part of the release validation workflow.

The earlier v0.1 Device Tree Explorer was also manually exercised with Raspberry Pi 5 and two Renesas R-Car DTB configurations for parsing, tree browsing, property inspection, search, navigation, and reload behavior.

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: unsupported or ambiguous address semantics produce structured warnings rather than fabricated mappings.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: parsing/decoding stays separate from addressing interpretation and future runtime correlation.
- **Keep the core generic**: platform-specific support should build on the same parser, model, and addressing contracts.
- **Preserve provenance**: translated addresses retain the bus/range steps that produced them.

## Project status

VMAX v0.2.0 is the second public development release. It adds static Device Tree memory/MMIO semantics and address-space visualization while the project remains pre-1.0.

The next milestone is **v0.3 — Linux Runtime Explorer**, which will add `/sys` and `/proc` runtime data as the foundation for Device Tree ↔ runtime correlation.
