# VMAX

VMAX is a Linux hardware explorer. V0.1 focuses on loading a DTB file and exposing
the parsed Device Tree through a small FastAPI backend.

## Backend Setup

Install backend dependencies:

```powershell
uv sync --extra dev
```

Enable real DTB parsing with `pylibfdt`:

```powershell
uv sync --extra dev --extra dtb
```

`pylibfdt` is optional in the project metadata because it needs native build
tools on some platforms. Linux or the target board is the recommended
environment for real DTB parsing.

## Run Backend

```powershell
$env:PYTHONPATH = "backend"
$env:VMAX_DTB_PATH = "C:\path\to\board.dtb"
uv run uvicorn app.main:app --reload
```

API endpoints:

```text
GET /api/v1/metadata
GET /api/v1/devicetree
```

## Tests

```powershell
$env:PYTHONPATH = "backend"
uv run --extra dev python -m unittest discover -s backend/tests -v
```

## Frontend Contract

The V0.1 frontend starts with TypeScript models and a small API client only.
Install frontend dependencies and typecheck when Node.js is available:

```powershell
cd frontend
npm install
npm run typecheck
```
