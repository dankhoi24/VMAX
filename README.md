# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and grows toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, runtime events, diagnostics, and SoC-specific plugins.

> **v0.5.0 — Device Dependencies & IRQ Topology:** adds explicit hardware dependency modeling, Linux runtime IRQ collection/correlation, and an interactive focus graph on top of the v0.4 DT ↔ Linux runtime correlation foundation.

## Why VMAX

Low-level Linux and embedded debugging often requires jumping between multiple views of the same hardware:

- Device Tree source / DTB
- `/sys` and `/proc`
- driver bindings
- MMIO and reserved memory
- clocks, resets, power domains, DMA and IOMMU dependencies
- IRQ routing and Linux IRQ state
- DMA/IOMMU mappings
- runtime events

VMAX aims to bring those views into one consistent model instead of treating them as separate tools and files.

## v0.5.0 scope

VMAX v0.5.0 extends the static/runtime correlation foundation with explicit dependency and IRQ topology:

```text
Device Tree
    |
    v
Dependency extraction
    |
    +-- clock
    +-- reset
    +-- power domain
    +-- DMA
    +-- IOMMU
    +-- interrupt
            |
            v
     IRQ correlation
            |
            v
     Linux Runtime IRQ
            |
            v
    Dependency API / UI
            |
            v
       Focus Graph
```

Implemented in v0.5.0:

- all v0.1.0 Device Tree parsing, browsing, property inspection, and search capabilities
- all v0.2.0 Device Tree addressing, `reg` / `ranges` interpretation, translation tracing, and physical address-space visualization
- all v0.3.0 Linux runtime, local transport, and SSH runtime collection capabilities
- all v0.4.0 DT ↔ runtime-device ↔ driver and `/proc/iomem` correlation capabilities
- dependency domain for clock, reset, power-domain, DMA, IOMMU, and interrupt relationships
- Device Tree dependency extraction with phandle/provider resolution, named entries, specifier preservation, and provenance
- explicit and natural `interrupt-parent` handling plus `interrupts-extended`
- Linux runtime IRQ collection from `/proc/interrupts` with supplemental `/sys/kernel/irq` and `/proc/irq` metadata
- GIC SPI/PPI canonical hardware IRQ identity handling
- conservative DT interrupt ↔ Linux runtime IRQ correlation using controller + HWIRQ identity
- explicit dependency/correlation states: `resolved`, `unresolved`, `unavailable`, and `ambiguous`
- partial-source semantics: usable static topology remains available when runtime IRQ collection is incomplete or unavailable
- device-centric dependency API and runtime IRQ API
- frontend Runtime Interrupts explorer
- frontend Device Dependencies explorer with search, warnings, static/runtime status separation, and ambiguous IRQ candidates
- interactive dependency focus graph with provider navigation and explicit relationship direction

### Dependency semantics

VMAX models dependency direction as:

```text
consumer -> provider
```

For example, an IMR device can depend on a CPG clock provider even though the physical clock signal travels from CPG to IMR. Dependency direction describes service/resource dependency, not electrical signal direction.

Runtime IRQ correlation is modeled separately:

```text
consumer -> interrupt controller -> Linux IRQ
```

The first edge is a static dependency; the second is a runtime mapping/correlation. A resolved relationship means VMAX found a unique provider or runtime identity. It does **not** prove the hardware is healthy or active.

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
- **v0.3 — Linux Runtime Explorer**: `/sys`, `/proc`, runtime devices/drivers, `/proc/iomem`, local/SSH transport — **complete**
- **v0.4 — DT ↔ Runtime Correlation**: DT ↔ runtime-device ↔ driver and physical-resource correlation — **complete**
- **v0.5 — Dependencies & IRQ Topology**: dependency extraction, runtime IRQ correlation, dependency UI, focus graph — **complete**
- **v0.6 — Memory / DMA / IOMMU Foundation** — **next**
- **v0.7 — Observability & Runtime Events**
- **v0.8 — Flow Diagnostics**
- **v0.9 — R-Car Platform Plugin**
- **v1.0 — Stable Debugging Platform**

## Repository layout

```text
backend/
├── app/
│   ├── addressing/
│   ├── api/
│   ├── collectors/
│   ├── correlation/
│   ├── dependency/
│   ├── devicetree/
│   ├── interrupts/
│   ├── model/
│   ├── runtime/
│   └── services/
└── tests/

frontend/
├── src/
│   ├── api/
│   ├── components/
│   ├── graph/
│   ├── models/
│   ├── search/
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

## Run VMAX

VMAX can inspect either the local Linux machine running the backend or a remote embedded Linux target over SSH.

Typical embedded-target deployment:

```text
Developer browser
      |
      v
React / Vite on HOST :5173
      |
      | /api proxy
      v
FastAPI on HOST :8000
      |
      +--> local DTB file
      |
      +--> SSH --> Embedded Linux target
                    ├── /sys
                    └── /proc
```

The target does not need VMAX, Python, FastAPI, Node.js, or npm. It only needs SSH access plus the Linux runtime interfaces that VMAX reads.

### 1. Backend prerequisites

VMAX uses Python 3.11+ and `uv` for dependency management.

```bash
uv sync --extra dev --extra all
```

Optional dependency groups:

```text
dtb  -> pylibfdt
ssh  -> paramiko
all  -> dtb + ssh
```

### 2. Configure a Device Tree source

```bash
export VMAX_DTB_PATH=/path/to/board.dtb
```

For a running Linux target that exposes `/sys/firmware/fdt`, a convenient workflow is to copy that blob to the host and point `VMAX_DTB_PATH` at the copied file.

### 3. Local Linux runtime mode

If `VMAX_RUNTIME_SSH_TARGET` is not set, the backend collects runtime data from the local machine:

```bash
export PYTHONPATH=backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Remote SSH runtime mode

```bash
export VMAX_RUNTIME_SSH_TARGET=192.168.0.2
export VMAX_RUNTIME_SSH_USER=root
```

Authentication may use a key:

```bash
export VMAX_RUNTIME_SSH_KEY=/path/to/private_key
```

or password:

```bash
read -s -p "Target password: " VMAX_RUNTIME_SSH_PASSWORD
export VMAX_RUNTIME_SSH_PASSWORD
```

Optional settings:

```bash
export VMAX_RUNTIME_SSH_PORT=22
export VMAX_RUNTIME_SYSFS_ROOT=/sys
export VMAX_RUNTIME_PROC_ROOT=/proc
```

VMAX verifies SSH host keys by default. For a controlled lab target where accepting an unknown key is intentional:

```bash
export VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY=1
```

Start the backend:

```bash
export PYTHONPATH=backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Useful endpoints:

```text
GET /api/v1/metadata
GET /api/v1/devicetree
GET /api/v1/addressing
GET /api/v1/runtime/metadata
GET /api/v1/runtime/devices
GET /api/v1/runtime/drivers
GET /api/v1/runtime/iomem
GET /api/v1/runtime/interrupts
GET /api/v1/correlation/devices
GET /api/v1/dependencies/devices
```

### 5. Start the frontend

From `frontend/`:

```bash
npm install
npm run dev -- --host 0.0.0.0
```

Vite normally starts on port `5173` and proxies `/api` to the backend on port `8000`.

### 6. Expected result

The browser provides:

- Device Tree navigation, properties, search, addressing, and address-space visualization
- Linux runtime system/device/driver and `/proc/iomem` exploration
- DT ↔ runtime-device ↔ driver and physical-resource correlation
- runtime interrupt inventory with controller, HWIRQ, trigger, action, counts, and source metadata
- device dependency inspection for clock, reset, power-domain, DMA, IOMMU, and interrupt resources
- explicit static vs runtime resolution status
- structured warnings without hiding usable partial data
- ambiguous runtime IRQ candidates without guessing
- interactive dependency focus graph with consumer → provider direction and provider → IRQ runtime mapping

## Tests

Backend:

```bash
export PYTHONPATH=backend
uv run --extra dev --extra all python -m unittest discover -s backend/tests -v
```

Frontend:

```bash
cd frontend
npm test
npm run typecheck
npm run build
```

## Validation

v0.5.0 has been validated through backend regression coverage plus frontend test, typecheck, production-build, and UI validation.

The v0.5 dependency/IRQ validation covers:

- dependency extraction for clock, reset, power-domain, DMA, IOMMU, and interrupt relationships
- provider resolution and preserved DT specifier/provenance data
- GIC SPI/PPI translation, including the regression where DT SPI 150 maps to canonical GIC HWIRQ 182 rather than raw 150
- resolved, unresolved, unavailable, and ambiguous runtime correlation semantics
- partial runtime failure while preserving static dependency topology
- device-centric API serialization
- Runtime Interrupts and Device Dependencies frontend views
- dependency focus graph topology, provider deduplication, IRQ deduplication, ambiguous candidates, unavailable runtime state, and provider navigation

Frontend release validation for v0.5.0:

```text
21 test files
125 tests passed
TypeScript typecheck passed
Production build passed
UI validation passed
```

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: unsupported or ambiguous semantics produce structured warnings rather than fabricated mappings.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: parsing/decoding stays separate from addressing interpretation and runtime correlation.
- **Keep static and runtime evidence explicit**: static dependency resolution and runtime correlation are separate facts.
- **Use stable identity evidence**: avoid guessing device or IRQ identity from names alone.
- **Treat `/proc/iomem` as supporting address evidence**: range relationships do not prove ownership.
- **Keep the core generic**: platform-specific support should build on common parser, model, provider, and transport contracts.
- **Preserve provenance**: dependency references, translated addresses, runtime fields, and warnings retain their evidence source.
- **Prefer partial observability over fabricated certainty**: positive evidence remains usable, while unavailable or incomplete information never becomes a false negative conclusion.

## Project status

VMAX v0.5.0 is the fifth public development release. It extends the static/runtime correlation foundation with explicit hardware dependency modeling, Linux IRQ correlation, and dependency topology visualization.

The next milestone is **v0.6 — Memory / DMA / IOMMU Foundation**.
