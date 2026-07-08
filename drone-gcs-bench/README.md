# GCS Backend Gateway Benchmarking Suite

https://drive.google.com/file/d/1piZe1q5OxoBAqh-uU-K6AYxaWaxquzgh/view?usp=sharing

> Production-grade evaluation of 16 backend frameworks for a real-time Autonomous Drone Ground Control Station (GCS) telemetry bridge.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Go](https://img.shields.io/badge/Go-1.24-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📖 Overview

This repository hosts the benchmarking suite for evaluating modern backend frameworks under real-time telemetry streaming workloads. Designed for **Skyeris Aero Tech's Ground Control Station (GCS)**, the pipeline tests how frameworks handle high-throughput, low-latency concurrent traffic by ingesting raw drone data and broadcasting it to active clients.

Rather than running simple, artificial HTTP hello-world endpoints, every framework executes an identical real-time pipeline:
- **UDP MAVLink Ingestion:** Listening to telemetry packets sent from a fleet simulator.
- **Message Decoding:** Parsing raw binary payloads into structured GCS telemetry.
- **Shared Telemetry State:** Maintaining an in-memory thread-safe state representing the drone fleet.
- **Metrics Collection:** Collecting request rates and processing latencies.
- **WebSocket Broadcast:** Instantly streaming telemetry updates to connected dashboard clients.

---

## 🚀 Features

- **Multi-Language Coverage:** Python, Go, and TypeScript candidates evaluated under identical workloads.
- **Real MAVLink Simulator:** Includes a lightweight, high-fidelity synthetic telemetry generator.
- **Docker-Out-of-Docker Runner:** Runs the entire pipeline sequentially via a single orchestration container.
- **Automatic Report Generation:** Produces clean Markdown reports and responsive, visually stunning HTML dashboards.
- **GitHub Actions CI Quality Gate:** Enforces linting, formatting, candidate unit testing, and full-pipeline smoke tests.

---

## 🏗️ Architecture

```text
Telemetry Simulator
        │ (UDP MAVLink Packets on 14550)
        ▼
   [Candidate] Gateway Bridge (e.g. nethttp, fastapi, hono)
        │
        ├──> Telemetry Parser & System ID Decoder
        ├──> Shared State Update (In-Memory Fleet Status)
        ├──> Prometheus Metrics Exposer (/metrics on 8000)
        └──> WebSocket Broadcast (/ws/telemetry on 8000)
                │
                ▼
      k6 WebSocket Clients (Dashboard Simulation)
```

---

## 📂 Repository Layout

```text
├── .github/workflows/      # GitHub Actions CI scripts
├── benchmarks/
│   ├── k6/                 # k6 load testing scenarios and running scripts
│   │   ├── scripts/        # Telemetry simulator (mavlink_sim.py) and runner
│   │   └── scenarios/      # JS websocket workloads
│   ├── validation/         # E2E validation quality gates and contracts
│   ├── run_campaign.py     # Main campaign orchestrator
│   └── generate_report.py  # Markdown and HTML report compiler
├── candidates/             # Candidate GCS Gateway implementations
│   ├── go/                 # net/http, Gin, Echo, Fiber, Chi bridges
│   ├── python/             # FastAPI, Litestar, Sanic, Starlette, aiohttp bridges
│   └── typescript/         # Express, Hono, uWebSockets, Fastify, NestJS, Elysia gateways
├── results/                # Raw results folder
│   ├── <candidate>/        # Test run JSON metrics
│   └── reports/            # Compiled Markdown & HTML benchmark reports
├── Dockerfile              # Orchestrator runner Dockerfile
├── docker-compose.yml      # Orchestration compose definition
├── docker-entrypoint.sh    # Main test automation startup script
└── README.md
```

---

## 📊 Benchmark Methodology

The benchmark subjects each framework to a series of load profiles designed to stress their network, concurrency, and serialization capabilities:
- **Workload:** 10s runs per candidate per drone count scaling tier.
- **Telemetry Update Frequency:** 10 Hz (10 packets/sec per drone).
- **Concurrency Tiers:** 1, 10, and 100 virtual drones.
- **Active Subscribers:** 2 constant virtual clients listening to the telemetry stream via WebSockets.
- **Telemetry Payload Size:** ~150-250 bytes (decoding Attitude, Heartbeat, Global Position, and System Status).

---

## 💻 Supported Frameworks

| Ecosystem | Framework / Gateway | Bridge Directory |
| :--- | :--- | :--- |
| **Go** | `net/http` (stdlib) | [nethttp-bridge](candidates/go/nethttp-bridge/) |
| | Gin | [gin-bridge](candidates/go/gin-bridge/) |
| | Echo | [echo-bridge](candidates/go/echo-bridge/) |
| | Fiber | [fiber-bridge](candidates/go/fiber-bridge/) |
| | Chi | [chi-bridge](candidates/go/chi-bridge/) |
| **Python** | FastAPI | [fastapi-bridge](candidates/python/fastapi-bridge/) |
| | Litestar | [litestar-bridge](candidates/python/litestar-bridge/) |
| | Sanic | [sanic-bridge](candidates/python/sanic-bridge/) |
| | Starlette | [starlette-bridge](candidates/python/starlette-bridge/) |
| | aiohttp | [aiohttp-bridge](candidates/python/aiohttp-bridge/) |
| **TypeScript** | Express | [express-gateway](candidates/typescript/express-gateway/) |
| | Hono | [hono-gateway](candidates/typescript/hono-gateway/) |
| | uWebSockets.js | [uwebsockets-bridge](candidates/typescript/uwebsockets-bridge/) |
| | Fastify | [fastify-gateway](candidates/typescript/fastify-gateway/) |
| | NestJS | [nestjs-gateway](candidates/typescript/nestjs-gateway/) |
| | Elysia | [elysia-gateway](candidates/typescript/elysia-gateway/) |

---

## 🐳 Docker Quickstart (Recommended)

Reviewers can reproduce the entire evaluation campaign on any host machine running **Docker Desktop** with a single command. 

```bash
docker compose up --build
```

---

# ⭐ Reviewer Quick Start

The benchmark is fully reproducible using Docker Desktop.

After cloning the repository, simply run:

```bash
docker compose up --build
```

The framework will automatically:

- Build all backend framework containers
- Execute the complete benchmark campaign
- Collect benchmark metrics
- Generate Markdown reports
- Generate HTML reports
- Save all benchmark artifacts inside `results/`

No additional setup is required beyond Docker Desktop.

---

### What this command does:
1. Builds the core **Benchmark Orchestrator** environment.
2. Scans for candidate frameworks and builds all 16 Docker images locally.
3. Spawns each candidate container sequentially inside an isolated environment.
4. Executes the k6 load testing suite using the local MAVLink telemetry generator.
5. Saves results and generates polished analytical reports.
6. Cleans up all resources and exits cleanly.

---

## 🛠️ Local Development

If you prefer to run the benchmark runner on your local system outside of Docker (Docker Desktop must still be running to host the candidate containers):

### 1. Set up Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r benchmarks/workload/requirements.txt
```

### 2. Install k6
Follow the official [k6 installation guide](https://grafana.com/docs/k6/latest/set-up/install-k6/) for your system.

---

## 🏃 Running Benchmarks

Once your local environment is configured, execute the campaign:

```bash
# Run the benchmark campaign
python3 benchmarks/run_campaign.py

# Compile Markdown & HTML reports
python3 benchmarks/generate_report.py
```

---

## 📈 Generated Reports

Benchmark outputs are formatted and written to:
- **Markdown Summary:** [results/reports/benchmark_report.md](results/reports/benchmark_report.md)
- **Interactive HTML Dashboard:** [results/reports/benchmark_report.html](results/reports/benchmark_report.html)

The HTML dashboard uses a modern dark theme with responsive styling, composite scoring ranking bars, and comprehensive latency distributions suitable for presentation.

---

## 📂 Results Folder

The raw metrics collected during the test execution are saved in [results/campaign_results.json](results/campaign_results.json). Each entry details the throughput rates, percentile latencies, error counts, and resources utilized by the framework during that specific concurrency tier run.

---

## 🔍 Troubleshooting

- **Docker Permission Errors:** Ensure your local user has access to `/var/run/docker.sock`. On Linux hosts, you may need to add your user to the `docker` group or run with `sudo`.
- **Port Conflict (8000 / 14550):** Ensure no local process is listening on TCP port 8000 or UDP port 14550 before starting the campaign.
- **ZeroDivisionError / Empty Runs:** If running manually, ensure that the candidate images were successfully built (`docker images` should show `nethttp-bridge:latest`, `fastapi-bridge:latest`, etc.) before initiating `run_campaign.py`.

---

## 🔮 Future Work

- **MQTT Broker Integration:** Benchmarking message brokers under MQTT ingestion.
- **Fleet Scale Up:** Evaluating scaling performance up to 5,000 concurrent drone nodes.
- **Network Fault Injection:** Incorporating `Pumba` packet-delay and packet-loss routines directly into the orchestrator loop.
- **CPU / Memory Profiling:** Integrating OS-level resource usage capture in the reports.

---

## 📝 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
