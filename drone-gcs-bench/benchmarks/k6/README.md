# Drone GCS Benchmark Suite (k6)

Reusable k6 benchmark suite for all backend candidates:
- FastAPI
- Litestar
- Echo
- Gin
- Fastify
- Hono

The same scripts run unchanged across frameworks; only `BASE_URL` (and optionally `WS_URL`) changes.

## Directory structure

```text
benchmarks/k6/
├── config/
│   ├── profiles.js
│   ├── runtime.js
│   └── thresholds.js
├── lib/
│   ├── bootstrap.js
│   ├── metrics.js
│   └── telemetry.js
├── scenarios/
│   ├── health.js
│   ├── registration.js
│   ├── telemetry.js
│   ├── websocket.js
│   └── validation_e2e.js
├── scripts/
│   └── run-profile.sh
└── results/
```

## Shared configuration

Environment variables (supported in all scenarios):
- `BASE_URL` (default: `http://localhost:8000`)
- `WS_URL` (optional; auto-derived from `BASE_URL`)
- `PROFILE` (`100`, `500`, `1000`, `5000`)
- `DURATION` (overrides profile duration)
- `VUS` (overrides profile VUs)
- `DRONE_COUNT` (overrides profile drone count)
- `TELEMETRY_RATE` (events/sec/drone; overrides profile)
- `REGISTER_DRONES` (`true`/`false`, default `true`)

Profile defaults:
- `100`: 100 drones, 20 VUs, 2m, telemetry rate 2
- `500`: 500 drones, 60 VUs, 3m, telemetry rate 2
- `1000`: 1000 drones, 120 VUs, 4m, telemetry rate 2
- `5000`: 5000 drones, 300 VUs, 5m, telemetry rate 1

## Scenarios

- `scenarios/health.js`
  - Benchmarks `GET /api/v1/health`
- `scenarios/registration.js`
  - Benchmarks `POST /api/v1/drones/register`
- `scenarios/telemetry.js`
  - Benchmarks `POST /api/v1/telemetry` at profile load
- `scenarios/websocket.js`
  - Runs telemetry producers + WebSocket consumers against `/ws/telemetry`
  - Measures WebSocket latency and sequence-gap dropped messages
- `scenarios/validation_e2e.js`
  - Quality-gate scenario for strict WS broadcast behavior under deterministic telemetry feed

## Metrics captured

Built-in k6:
- `http_reqs` (requests/sec)
- `http_req_duration` (avg, p50, p95, p99)
- `http_req_failed` (failures)
- `data_sent`, `data_received` (throughput)

Custom:
- `benchmark_failure_rate`
- `benchmark_throughput_bytes_total`
- `ws_message_latency_ms`
- `ws_messages_dropped_total`
- `ws_messages_received_total`

## Run commands

From repository root:

```bash
cd benchmarks/k6
```

FastAPI example target:

```bash
BASE_URL=http://localhost:8000
```

Health benchmark profiles:

```bash
./scripts/run-profile.sh health 100 fastapi ${BASE_URL}
./scripts/run-profile.sh health 500 fastapi ${BASE_URL}
./scripts/run-profile.sh health 1000 fastapi ${BASE_URL}
./scripts/run-profile.sh health 5000 fastapi ${BASE_URL}
```

Registration benchmark profiles:

```bash
./scripts/run-profile.sh registration 100 fastapi ${BASE_URL}
./scripts/run-profile.sh registration 500 fastapi ${BASE_URL}
./scripts/run-profile.sh registration 1000 fastapi ${BASE_URL}
./scripts/run-profile.sh registration 5000 fastapi ${BASE_URL}
```

Telemetry benchmark profiles:

```bash
./scripts/run-profile.sh telemetry 100 fastapi ${BASE_URL}
./scripts/run-profile.sh telemetry 500 fastapi ${BASE_URL}
./scripts/run-profile.sh telemetry 1000 fastapi ${BASE_URL}
./scripts/run-profile.sh telemetry 5000 fastapi ${BASE_URL}
```

WebSocket benchmark profiles:

```bash
./scripts/run-profile.sh websocket 100 fastapi ${BASE_URL}
./scripts/run-profile.sh websocket 500 fastapi ${BASE_URL}
./scripts/run-profile.sh websocket 1000 fastapi ${BASE_URL}
./scripts/run-profile.sh websocket 5000 fastapi ${BASE_URL}
```

Validation scenario:

```bash
k6 run -e BASE_URL=${BASE_URL} scenarios/validation_e2e.js
```

Switch framework (same scripts, no code changes):

```bash
./scripts/run-profile.sh telemetry 500 litestar http://localhost:8100
./scripts/run-profile.sh telemetry 500 gin http://localhost:8200
./scripts/run-profile.sh telemetry 500 echo http://localhost:8300
./scripts/run-profile.sh telemetry 500 fastify http://localhost:8400
./scripts/run-profile.sh telemetry 500 hono http://localhost:8500
```
