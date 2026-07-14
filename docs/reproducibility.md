# Reproducibility Guide — GCS Backend Gateway Benchmarking

To reproduce the benchmark results on any system, follow these sequential steps.

---

## 🐳 Option 1: Docker Compose Workflow (Recommended)

This workflow requires zero local setup besides **Docker Desktop**. It runs the entire benchmark orchestrator inside an isolated environment and exports reports directly to the host filesystem.

### 1. Launch Docker Compose
In your terminal, navigate to the repository root and run:
```bash
docker compose up --build
```

### 2. Verify Output
Once the benchmark campaign completes, the generated reports are stored locally:
- Markdown Report: `results/reports/benchmark_report.md`
- Interactive HTML Dashboard: `results/reports/benchmark_report.html`

---

## 🛠️ Option 2: Local Development Execution

If you prefer to run the orchestration script directly on your host machine (note: Docker Desktop must still be running to build and host the candidate containers):

### 1. Build Candidate Docker Images
First, build the Docker images for all candidate frameworks:
```bash
docker build -t fastapi-bridge:latest candidates/python/fastapi-bridge/
docker build -t litestar-bridge:latest candidates/python/litestar-bridge/
docker build -t sanic-bridge:latest candidates/python/sanic-bridge/
docker build -t aiohttp-bridge:latest candidates/python/aiohttp-bridge/
docker build -t starlette-bridge:latest candidates/python/starlette-bridge/
docker build -t nethttp-bridge:latest candidates/go/nethttp-bridge/
docker build -t echo-bridge:latest candidates/go/echo-bridge/
docker build -t fiber-bridge:latest candidates/go/fiber-bridge/
docker build -t chi-bridge:latest candidates/go/chi-bridge/
docker build -t gin-bridge:latest candidates/go/gin-bridge/
docker build -t hono-gateway:latest candidates/typescript/hono-gateway/
docker build -t uwebsockets-bridge:latest candidates/typescript/uwebsockets-bridge/
docker build -t express-gateway:latest candidates/typescript/express-gateway/
```

### 2. Prepare Local Python Environment
Create a virtual environment and install requirements:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r benchmarks/workload/requirements.txt
```

### 3. Run Campaign Suite
Run the benchmark orchestrator:
```bash
python3 benchmarks/run_campaign.py
```
This script sequentially starts each candidate, triggers telemetry generator loads, runs k6 test scenarios, and saves metrics to `results/campaign_results.json`.

### 4. Compile Reports
Compile analytical markdown and HTML dashboards:
```bash
python3 benchmarks/generate_report.py
```
Reports will be written to `results/reports/`.
