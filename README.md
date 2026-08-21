# VMAX

VMAX is an **Embedded System Topology & Correlation Explorer** for understanding how firmware description, operating-system runtime state, and hardware resources relate to each other.

The project starts with Device Tree exploration and grows toward correlation across devices, drivers, MMIO, IRQs, DMA/IOMMU/IOVA, kernel symbols, snapshots, runtime events, and SoC-specific plugins.

> **v0.3.0 — Linux Runtime Explorer:** adds live Linux runtime inspection from `/sys` and `/proc`, including devices, driver bindings, system metadata, `/proc/iomem`, local collection, and remote SSH collection for embedded targets.

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

## v0.3.0 scope

VMAX v0.3.0 builds on the static Device Tree and address-space analysis from v0.1/v0.2 with a Linux runtime view:

```text
                         VMAX
                          |
          +---------------+---------------+
          |                               |
   Static Device Tree                Linux Runtime
          |                               |
        DTB file                     /sys + /proc
          |                               |
   pylibfdt parser                RuntimeProvider
          |                               |
   DeviceTree model          +------------+------------+
          |                  |                         |
   AddressingReport      Local transport           SSH transport
          |                  |                         |
          +------------------+-------------------------+
                             |
                         FastAPI
                             |
                         React UI
```

Implemented in v0.3.0:

- all v0.1.0 Device Tree parsing, browsing, property inspection, and search capabilities
- all v0.2.0 Device Tree addressing, `reg` / `ranges` interpretation, translation tracing, and physical address-space visualization
- Linux runtime domain models for system metadata, devices, drivers, resources, `/proc/iomem`, and structured warnings
- Linux system metadata from runtime sources, including hostname, `uname`, architecture normalization, and `/proc/cmdline`
- platform-device inventory from sysfs
- current driver binding metadata when a runtime device exposes a driver symlink
- runtime `of_node` sysfs metadata without claiming Device Tree correlation
- platform-driver inventory and bound-device information
- hierarchical `/proc/iomem` parsing and runtime physical address visualization
- partial-data semantics: inaccessible or missing runtime data becomes structured warnings instead of collapsing the whole scan
- local runtime transport for inspecting the machine running the backend
- SSH runtime transport for inspecting a remote embedded Linux target without installing VMAX, Python, FastAPI, or Node.js on the target
- secure SSH host-key verification by default, with an explicit opt-in for accepting unknown host keys in controlled lab environments
- frontend Runtime Device Browser and Runtime Address Map
- real-board validation using a Renesas R-Car Linux target over SSH

v0.3.0 intentionally does **not** yet claim Device Tree ↔ Linux runtime correlation. In particular, it does not infer that a Device Tree node owns a runtime device, that a static Device Tree region is owned by a particular runtime driver, or that a compatible string maps to a currently bound driver. Those correlations are the focus of v0.4.

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
- **v0.4 — DT ↔ Device ↔ Driver correlation** — **next**
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
- structured warnings for partial runtime data

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

v0.3.0 has been validated through backend regression testing, frontend test/typecheck/build validation, and manual runtime validation against a real Renesas R-Car Linux target over SSH.

The runtime validation covers:

- remote hostname and `uname` metadata
- architecture normalization
- `/proc/cmdline`
- platform-device inventory
- current driver bindings
- runtime `of_node` metadata
- platform-driver inventory
- `/proc/iomem`
- browser rendering of the runtime views
- remote collection through the SSH transport while the VMAX backend/frontend remain on the host

The v0.2.0 addressing semantics were also validated with a real Raspberry Pi 5 DTB through the production parser and addressing pipeline, including exact RAM/reserved-memory regions, simple-bus translation, translation provenance, multiple `reg` resources, addresses above 4 GiB, and conservative handling of unsupported PCI 3-cell address formats.

## Design principles

- **Preserve raw data**: decoded values never replace the original DTB bytes.
- **Prefer known semantics over heuristics**: property-name knowledge wins over byte-pattern guessing.
- **Be conservative when uncertain**: unsupported or ambiguous semantics produce structured warnings rather than fabricated mappings.
- **Keep libfdt behind an adapter boundary**: pylibfdt objects do not leak into the domain model.
- **Separate syntax from semantics**: parsing/decoding stays separate from addressing interpretation and runtime correlation.
- **Separate static and runtime truth**: Device Tree and Linux runtime views remain distinct until an explicit correlation layer connects them.
- **Keep the core generic**: platform-specific support should build on common parser, model, provider, and transport contracts.
- **Preserve provenance**: translated addresses retain the bus/range steps that produced them.
- **Prefer partial observability over fabricated certainty**: unavailable runtime information becomes a warning, not an invented value.

## Project status

VMAX v0.3.0 is the third public development release. It adds live Linux runtime visibility and remote SSH collection on top of the existing Device Tree and static address-space explorers.

The next milestone is **v0.4 — DT ↔ Device ↔ Driver correlation**, where the currently separate static and runtime models will begin to be connected explicitly.
