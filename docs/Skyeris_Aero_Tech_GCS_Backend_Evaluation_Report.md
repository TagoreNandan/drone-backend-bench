# GCS Backend Framework Evaluation Report

**Date:** July 3, 2026  
**Prepared By:** Skyeris Aero Tech Engineering Team  

---

## 1. What was benchmarked?
The evaluation covered 13 backend framework candidates across Go, TypeScript/Node.js, and Python, retrofitted to ingest high-frequency UDP MAVLink telemetry, decode binary frames, maintain telemetry state, serialize updates to MessagePack, and broadcast updates over WebSockets.

### Candidate Frameworks
*   **Go Candidates:** `net/http` (standard library), `Echo`, `Fiber` (built on `fasthttp`), `Chi`, and `Gin`.
*   **TypeScript / Node.js Candidates:** `uWebSockets.js` (C++ bindings), `Hono`, and `Express`.
*   **Python Candidates:** `aiohttp`, `Sanic`, `Starlette`, `FastAPI`, and `Litestar`.

### Excluded and Non-Ready Candidates
*   **Django + Channels (Python):** Excluded due to ORM sync blockages and Redis dependency complexity.
*   **Fastify Gateway (TypeScript):** Not ready (lacked UDP socket ingestion and MessagePack broadcast).
*   **NestJS Gateway (TypeScript):** Not ready (lacked UDP MAVLink Ingestion).
*   **Elysia Gateway (TypeScript/Bun):** Not ready (lacked standardized Docker packaging and metrics endpoints).

---

## 2. How was it benchmarked?
Candidates were evaluated using an automated, containerized pipeline:

```
[ MAVLink Simulator ] ──(UDP, Port 14550)──> [ Candidate Gateway ] ──(WS MessagePack)──> [ k6 Clients ]
```

### Ingestion & Broadcast Pipeline
1.  **UDP Ingestion:** Candidates listen on `0.0.0.0:14550` for UDP MAVLink packets from a simulator (`mavlink_sim.py`).
2.  **State Management:** Decoded telemetry is stored in an in-memory thread-safe state cache.
3.  **Serialization & Broadcast:** Telemetry updates are serialized to MessagePack and broadcasted to active WebSocket clients.
4.  **Metrics Ingestion:** Internal counters are exposed on Prometheus `/metrics` and `/health` endpoints.

### Load Test Execution
*   **Workload Profile:** Simulator drove 100 drones at 2 Hz, producing 200 packets/sec.
*   **Client Load:** 2 k6 virtual users upgraded HTTP connections to WebSockets and consumed MessagePack broadcasts.
*   **Sequence:** Each candidate ran in an isolated Docker container sequentially. Execution consisted of a 5-second warmup run (data discarded), followed by 10 consecutive 5-second test runs.

---

## 3. What was measured?
Performance and static footprint parameters were measured via k6 JSONL client logs, Docker image inspections, and source audits:

| Parameter | Method | Status | Evidence Source |
| :--- | :--- | :--- | :--- |
| **Concurrent connections** | Experimental Benchmark | Measured | `ws_connections_active` (k6 logs) |
| **Throughput (Binary vs JSON)** | Experimental Benchmark | Measured | `ws_messages_received_total` (k6 logs) |
| **Message push latency** | Experimental Benchmark | Not measured | Hardcoded `1.00` ms placeholder value |
| **MAVLink decode & re-serialize time** | Experimental Benchmark | Not measured | Server `/metrics` not exported to client logs |
| **Backpressure handling** | Code Inspection | Verified | Gateway `websocket_manager` (2048 buffer) |
| **Static deployment footprint** | Code Inspection | Verified | Docker base image & package dependencies |
| **Binary / deployment size** | Code Inspection | Verified | Local `docker images` storage records |
| **MAVLink library maturity** | Ecosystem Review | Verified | Dependency manifests (`package.json`, `go.mod`, etc.) |
| **Time-series DB driver quality** | Ecosystem Review | Verified | QuestDB / TimescaleDB client specifications |
| **MQTT client library maturity** | Ecosystem Review | Verified | client package registries |
| **Framework-native pub/sub support** | Ecosystem Review | Verified | Redis / NATS / Kafka client modules |

*Note: Runtime CPU, memory utilization, cold start times, reconnection handling, horizontal pub/sub scale, and failover behavior were not experimentally measured.*

---

## 4. What was observed?

### Ingestion Throughput and Deployment Footprint
Throughput values represent the mean WebSocket messages parsed and consumed per second over 10 consecutive runs. Docker sizes represent the static image footprints.

| Framework | Language | Mean (msg/s) | Median (msg/s) | Min (msg/s) | Max (msg/s) | Std Dev | 95th Pct | 99th Pct | Docker Size |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **nethttp** | Go | **2400.00** | 2400.00 | 2400.00 | 2400.00 | 0.00 | 2400.00 | 2400.00 | **~29 MB** |
| **fiber** | Go | **2400.00** | 2400.00 | 2400.00 | 2400.00 | 0.00 | 2400.00 | 2400.00 | **~29 MB** |
| **chi** | Go | **2400.00** | 2400.00 | 2400.00 | 2400.00 | 0.00 | 2400.00 | 2400.00 | **~29 MB** |
| **gin** | Go | **2400.00** | 2400.00 | 2400.00 | 2400.00 | 0.00 | 2400.00 | 2400.00 | **~29 MB** |
| **echo** | Go | **2384.00** | 2400.00 | 2240.00 | 2400.00 | 48.00 | 2400.00 | 2400.00 | **~29 MB** |
| **uwebsockets** | TypeScript | **1962.88** | 2004.00 | 1402.80 | 2167.20 | 204.83 | 2158.92 | 2165.54 | **~979 MB** |
| **aiohttp** | Python | **1931.56** | 1937.20 | 1809.20 | 2032.00 | 71.44 | 2030.56 | 2031.71 | **~380 MB** |
| **hono** | TypeScript | **1773.72** | 1781.00 | 1714.00 | 1812.00 | 29.61 | 1809.12 | 1811.42 | **~440 MB** |
| **express** | TypeScript | **1772.94** | 1813.20 | 1343.80 | 1991.60 | 181.01 | 1976.30 | 1988.54 | **~440 MB** |
| **sanic** | Python | **1728.72** | 1786.60 | 1480.80 | 1856.80 | 119.94 | 1840.60 | 1853.56 | **~380 MB** |
| **starlette** | Python | **1708.64** | 1735.40 | 1472.80 | 1937.60 | 130.58 | 1870.28 | 1924.14 | **~380 MB** |
| **fastapi** | Python | **1705.64** | 1718.40 | 1447.60 | 1916.80 | 143.43 | 1873.42 | 1908.12 | **~380 MB** |
| **litestar** | Python | **1703.60** | 1762.00 | 1402.00 | 1880.00 | 144.77 | 1859.66 | 1875.93 | **~380 MB** |

### Verification Audit Status
All 13 candidates underwent verification across five checkpoints, achieving **Execution Verified** status:

| Framework | Structural Compliance | Health Check | Prometheus Metrics | UDP Ingestion | MessagePack WS Broadcast | Overall Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **nethttp (Go)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **fiber (Go)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **chi (Go)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **gin (Go)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **echo (Go)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **uwebsockets (TS)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **aiohttp (Python)** | Compliant | Verified (`/api/v1/health`)| Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **hono (TS)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **express (TS)** | Compliant | Verified (`/health`) | Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **sanic (Python)** | Compliant | Verified (`/api/v1/health`)| Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **starlette (Python)**| Compliant | Verified (`/api/v1/health`)| Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **fastapi (Python)** | Compliant | Verified (`/api/v1/health`)| Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |
| **litestar (Python)**| Compliant | Verified (`/api/v1/health`)| Verified (`/metrics`) | Verified (14550/udp) | Verified (`/ws/telemetry`) | **Execution Verified** |

### Framework and Ecosystem Observations
*   **Go Candidates:** Achieved maximum throughput (2400.00 msg/s) and smallest deployment sizes (~29 MB). Standard `net/http` and `Chi` showed 0.00 throughput variance. `Fiber` and `Chi` minimize routing overhead, though runtime memory under active load was not measured.
*   **TypeScript Candidates:** `uWebSockets.js` achieved 1962.88 msg/s but has the largest Docker size (~979 MB). In ecosystem checks, `node-mavlink` exhibited camelCase serialization mismatches (`timeBootMs` vs standard `time_boot_ms`), which can lead to parsing errors. TS candidates utilizing `npx tsx` for on-the-fly transpilation inside containers may introduce runtime CPU compilation overhead.
*   **Python Candidates:** `aiohttp` led the class at 1931.56 msg/s. FastAPI and Litestar clustered around 1705 msg/s. ASGI event-loop scheduling and Pydantic serialization may introduce execution overhead, though this was not isolated experimentally. Python benefits from `pymavlink`, the most mature and compliant MAVLink parser library checked.

---

## 5. What limitations exist?
1.  **Mocked Latency Metric:** End-to-end packet transmission latency was not experimentally measured due to isolated clock spaces. The `1.00` ms average latency is a hardcoded placeholder from the client script and must not be used for speed comparisons.
2.  **Workload Scale Overrides:** The shell runner script `run-profile.sh` hardcoded simulator settings to 100 drones @ 2Hz for the WebSocket scenario, neutralizing environment variables for smaller drone configurations.
3.  **Unmeasured Runtime CPU & Memory Utilization:** CPU and memory utilization under active load were not monitored or captured. Resource assessments are limited to static Docker image sizes and code inspections.
4.  **Hypervisor Overhead:** Virtualized Linux socket and storage layers inside Docker Desktop on macOS may introduce translation overhead not present in bare-metal deployments.
5.  **Small Statistical Sample:** Tests were limited to 10 runs of 5 seconds each, which is insufficient to evaluate long-term memory leaks, garbage collection spikes, or socket exhaustion.

---

## 6. What conclusions are supported by the measurements?
The measured throughput and static image sizes support a polyglot architecture for distinct components of the telemetry stack:

1.  **Go Candidates (`net/http` or `Chi`):** Preferred choice for edge telemetry ingestion bridges where low static image size (~29 MB) and maximum ingestion throughput (2400 msg/s) are required. Deployments on constrained target hardware must be validated independently.
2.  **Python Candidates (`FastAPI`):** Preferred choice for the cloud control plane and fleet management APIs. The throughput delta compared to Go is negligible for REST/CRUD control operations, and the framework provides OpenAPI generation and direct integration with mature `pymavlink` parser scripts.
3.  **TypeScript Candidates (`uWebSockets.js` or `Hono`):** Preferred choice for WebSocket broadcasting gateways when isomorphic frontend-backend type sharing is required. `uWebSockets.js` provides the highest non-Go throughput (1962.88 msg/s) under tested configurations.
