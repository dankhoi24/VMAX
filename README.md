# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and is designed to grow toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, kernel symbols, snapshots, and SoC-specific plugins.

> Status: early development. V0.1 currently provides DTB parsing, a FastAPI backend, a TypeScript API client, and a React Device Tree browser.

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

The current implementation focuses on loading a DTB and exposing it through a browser-based Device Tree explorer:

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
  |
  v
DeviceTreeCollector / DeviceTreeState
  |
  v
FastAPI + Pydantic API schema
  |
  | JSON
  v
TypeScript API client
  |
  v
React DeviceTreeView
```

Implemented pieces include:

- `DeviceTree`, `DeviceTreeNode`, `DeviceTreeProperty`, and `ParseResult` domain models
- conservative property decoding for boolean, string, string-list, cell, and unknown values
- direct DTB parsing through `pylibfdt`
- recursive node/property traversal
- preservation of raw property bytes
- Device Tree collector and current-source state
- FastAPI endpoints for metadata and the parsed Device Tree
- Pydantic response schemas and OpenAPI contract
- TypeScript API models and API client
- React/Vite Device Tree browser with recursive expand/collapse
- backend, API-client, and frontend component tests
- validation with a Raspberry Pi 5 DTB

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

With both processes running, the request flow is:

```text
Browser
  |
  v
React / Vite :5173
  |
  | /api/v1/devicetree
  v
Vite proxy
  |
  v
FastAPI :8000 (WSL)
  |
  v
DeviceTreeCollector
  |
  v
pylibfdt
  |
  v
DTB
```

The browser should display the root `/` node, its immediate children, a total node count, and expandable/collapsible Device Tree nodes.

## Tests

Run backend tests from the repository root in the Python environment:

```bash
export PYTHONPATH=backend
uv run --extra dev python -m unittest discover -s backend/tests -v
```

Run frontend tests and type checking from `frontend/`:

```bash
npm test
npm run typecheck
```

The real-DTB backend path requires the `libfdt` Python binding (`pylibfdt`).

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: ambiguous values remain `UNKNOWN` rather than being misclassified.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: V0.1 decodes representation; later versions interpret `reg`, `ranges`, IRQs, and other hardware meaning.
- **Keep the core generic**: Raspberry Pi and R-Car should use the same parser/model contracts.

## Project status

VMAX is currently under active early development. Interfaces, package layout, and roadmap details may still change before the first public release.
