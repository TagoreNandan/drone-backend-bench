# 🚁 Skyeris Aero Tech – Backend Framework Evaluation

> Production-oriented evaluation of backend frameworks for a real-time Autonomous Drone Ground Control Station (GCS).

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Go](https://img.shields.io/badge/Go-1.24-00ADD8)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 Overview

This project evaluates modern backend frameworks for a real-time drone telemetry platform.

Instead of benchmarking generic HTTP APIs, every framework executes the same telemetry pipeline:

```text
Telemetry Simulator
        │
        ▼
UDP MAVLink
        │
        ▼
Telemetry Parser
        │
        ▼
Shared Telemetry State
        │
        ▼
Metrics
        │
        ▼
WebSocket Broadcast
        │
        ▼
Dashboard Clients
```

The objective is to determine the most suitable backend architecture for Skyeris Aero Tech's Ground Control Station.

---

## Supported Frameworks

### Go

- net/http
- Gin
- Echo
- Fiber
- Chi

### Python

- FastAPI
- Starlette
- Sanic
- Litestar
- aiohttp

### TypeScript

- Express
- Hono
- uWebSockets.js
- Fastify
- NestJS
- Elysia

---

## Repository Structure

```text
benchmarks/
candidates/
docs/
results/

BENCHMARK_SPEC.md
```

---

## Quick Start

Clone the repository

```bash
git clone https://github.com/TagoreNandan/drone-backend-bench.git

cd drone-backend-bench
```

Run Docker

```bash
docker compose up
```

Run Benchmark

```bash
python benchmarks/run_campaign.py
```

Generate Report

```bash
python benchmarks/generate_report.py
```

---

## Verification

Every implementation is verified using:

- Docker build
- Docker runtime
- Health endpoint
- Metrics endpoint
- UDP telemetry
- WebSocket broadcast
- End-to-end telemetry flow

---

## Benchmark Methodology

Every framework executes an identical workload:

- UDP MAVLink ingestion
- Telemetry decoding
- Shared state update
- Metrics collection
- WebSocket broadcasting

Measured metrics include:

- Throughput
- Verification status
- Docker footprint
- End-to-end functionality

Frameworks are also evaluated using architectural and ecosystem criteria.

---

## Documentation

- Benchmark Report
- Framework Comparison
- Methodology
- Reproducibility
- Threats to Validity
- Benchmark Specification

Located in `/docs`.

---

## Results

The complete benchmark campaign and reports are included in `/results`.

---

## Future Work

- MQTT integration
- Fleet-scale benchmarking
- Real latency instrumentation
- Multi-drone simulation
- CPU and memory profiling

---

## License

MIT License

---

## Acknowledgements

Developed as part of the backend architecture evaluation for Skyeris Aero Tech's Autonomous Drone Ground Control Station.
