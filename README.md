# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and grows toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, kernel symbols, snapshots, runtime events, and SoC-specific plugins.

> **v0.4.0 — DT ↔ Linux Runtime Correlation:** connects static Device Tree descriptions with Linux runtime devices, bound drivers, and `/proc/iomem` physical-resource evidence using conservative, provenance-preserving correlation.

## Why VMAX

Low-level Linux and embedded debugging often requires jumping between multiple views of the same hardware:

- Device Tree source / DTB
- `/sys` and `/proc`
- driver bindings
- MMIO and reserved memory
- IRQ routing
- DMA and IOMMU mappings
- kernel symbols and runtime events

VMAX aims to bring those views into one consistent model instead of treating them as separate tools and files.

## v0.4.0 scope

VMAX v0.4.0 connects the static Device Tree/addressing pipeline from v0.1/v0.2 with the Linux runtime explorer introduced in v0.3:

```text
               Static                     Runtime
                 |                           |
            DeviceTree                 RuntimeDevice
                 |                           |
         AddressingReport              RuntimeDriver
                 |                           |
                 |                       /proc/iomem
                 |                           |
                 +------------+--------------+
                              |
                     CorrelationService
                              |
                              v
                     CorrelationReport
                              |
                         FastAPI API
                              |
                         React UI
```

Implemented in v0.4.0:

- all v0.1.0 Device Tree parsing, browsing, property inspection, and search capabilities
- all v0.2.0 Device Tree addressing, `reg` / `ranges` interpretation, translation tracing, and physical address-space visualization
- all v0.3.0 Linux runtime, local transport, and SSH runtime collection capabilities
- exact Device Tree ↔ Linux runtime-device identity correlation through resolved runtime `of_node`
- runtime-device ↔ bound-driver association using observed sysfs evidence
- translated DT physical-range ↔ `/proc/iomem` correlation
- explicit address relations: `exact`, `iomem_contains_dt`, `dt_contains_iomem`, `overlap`, `none`, `ambiguous`, and `unavailable`
- preservation of all `/proc/iomem` candidates for ambiguous relations instead of guessing ownership
- conservative semantics: physical address coincidence is supporting evidence, not proof that a device or driver owns a DT MMIO region
- partial-source semantics where positive evidence remains usable while negative conclusions require complete source collection
- explicit distinction between `unmatched` and `unavailable`
- structured correlation warnings with source, DT-node, and runtime-device provenance
- `GET /api/v1/correlation/devices`
- frontend DT Runtime Correlation explorer with search, status filters, identity, driver, address-relation, warnings, and ambiguous-candidate views

### Correlation semantics

VMAX uses runtime `of_node` as the primary DT ↔ runtime-device identity evidence.

VMAX deliberately does **not** infer device identity from compatible strings, device names, or physical-address coincidence.

`/proc/iomem` correlation describes how translated DT physical ranges relate to Linux's physical resource tree. It does not by itself prove device or driver ownership of a region.

Runtime resources are reported only when a real runtime source exposes them. VMAX does not fabricate generic platform-device resources from interfaces that Linux does not provide as a stable platform-bus ABI.

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
- **v0.4 — DT ↔ Device ↔ Driver correlation** — **complete**
- **v0.5 — IRQ and dependency graph** — **next**
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
│   ├── correlation/
│   ├── model/
│   ├── parsers/
│   ├── runtime/
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

Install the backend with the features needed for Device Tree and SSH runtime inspection:

```bash
uv sync --extra dev --extra all
```

The optional dependency groups are:

```text
dtb  -> pylibfdt
ssh  -> paramiko
all  -> dtb + ssh
```

### 2. Configure a Device Tree source

VMAX's static Device Tree view is independent from the Linux runtime view. Select a DTB file with:

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

Configure the remote target before starting the backend:

```bash
export VMAX_RUNTIME_SSH_TARGET=192.168.0.2
export VMAX_RUNTIME_SSH_USER=root
```

Authentication may use a key:

```bash
export VMAX_RUNTIME_SSH_KEY=/path/to/private_key
```

or a password:

```bash
read -s -p "Target password: " VMAX_RUNTIME_SSH_PASSWORD
export VMAX_RUNTIME_SSH_PASSWORD
```

Optional SSH configuration:

```bash
export VMAX_RUNTIME_SSH_PORT=22
export VMAX_RUNTIME_SYSFS_ROOT=/sys
export VMAX_RUNTIME_PROC_ROOT=/proc
```

VMAX verifies SSH host keys by default. For a controlled lab target where accepting an unknown key is intentional, this can be explicitly enabled:

```bash
export VMAX_RUNTIME_SSH_ACCEPT_UNKNOWN_HOST_KEY=1
```

Do not use that setting as a substitute for host-key verification in normal deployments.

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
GET /api/v1/correlation/devices
```

### 5. Start the frontend

Install a current Node.js LTS release, then from `frontend/`:

```bash
npm install
npm run dev -- --host 0.0.0.0
```

Vite normally starts on port `5173` and proxies `/api` to the backend on port `8000`.

### 6. Expected result

With the static DTB and runtime backend configured, the browser provides:

- expandable/collapsible Device Tree navigation
- selected-node property inspection
- decoded property values with optional raw-hex inspection
- Device Tree search and navigation
- semantic `reg` / `ranges` addressing information
- bus-to-CPU Translation Trace
- static physical Address Space Map
- Linux runtime system metadata
- runtime platform-device and driver browsing
- bound-driver and runtime `of_node` metadata when exposed by sysfs
- runtime `/proc/iomem` visualization
- DT ↔ runtime-device identity correlation
- runtime-device ↔ driver correlation
- DT physical-range ↔ `/proc/iomem` relation visualization
- explicit `unmatched` vs `unavailable` semantics
- ambiguous address candidates and structured warnings

## Tests

Run backend tests from the repository root:

```bash
export PYTHONPATH=backend
uv run --extra dev --extra all python -m unittest discover -s backend/tests -v
```

Run frontend tests, type checking, and the production build from `frontend/`:

```bash
npm test
npm run typecheck
npm run build
```

## Validation

v0.4.0 has been validated through backend regression testing, frontend test/typecheck/build validation, and real-target correlation validation with the Linux runtime collection pipeline.

The v0.4 validation covers:

- DT ↔ runtime-device matching through resolved `of_node`
- runtime-device ↔ driver association
- translated DT physical ranges against `/proc/iomem`
- exact, containment, overlap, none, ambiguous, and unavailable address semantics
- partial-source behavior where positive evidence is retained while negative conclusions require complete scans
- `unmatched` vs `unavailable`
- frontend rendering of correlation state, address evidence, driver state, warnings, and ambiguous candidates

The v0.3 runtime foundation was validated against a real Renesas R-Car Linux target over SSH, including runtime metadata, platform devices, current driver bindings, runtime `of_node`, platform drivers, `/proc/iomem`, and browser rendering while the backend/frontend remained on the host.

The v0.2 addressing semantics were also validated with a real Raspberry Pi 5 DTB through the production parser and addressing pipeline, including exact RAM/reserved-memory regions, simple-bus translation, translation provenance, multiple `reg` resources, addresses above 4 GiB, and conservative handling of unsupported PCI 3-cell address formats.

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: unsupported or ambiguous semantics produce structured warnings rather than fabricated mappings.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: parsing/decoding stays separate from addressing interpretation and runtime correlation.
- **Keep static and runtime evidence explicit**: Device Tree and Linux runtime remain separate sources connected only through an explicit correlation layer.
- **Use `of_node` as primary identity evidence**: do not infer identity from names, compatible strings, or address coincidence.
- **Treat `/proc/iomem` as supporting address evidence**: range relationships do not prove ownership.
- **Keep the core generic**: platform-specific support should build on common parser, model, provider, and transport contracts.
- **Preserve provenance**: translated addresses and warnings retain the evidence that produced them.
- **Prefer partial observability over fabricated certainty**: positive evidence remains usable, while unavailable or incomplete information never becomes a false negative conclusion.

## Project status

VMAX v0.4.0 is the fourth public development release. It connects the static Device Tree/address-space explorers with Linux runtime devices, drivers, and `/proc/iomem` evidence through an explicit correlation layer.

The next milestone is **v0.5 — IRQ and dependency graph**.
