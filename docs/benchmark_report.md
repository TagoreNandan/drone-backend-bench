# GCS Telemetry Bridge Benchmark Report

**Execution Date:** July 3, 2026  

---

## 1. What was benchmarked?
Thirteen candidate framework implementations (Go, TypeScript, Python) retrofitted to decode MAVLink telemetry packets over UDP, encode them into binary MessagePack, and broadcast them to active WebSocket subscribers.

---

## 2. How was it benchmarked?
Each candidate ran inside an isolated Docker container on an Apple M1 host. Telemetry load (100 drones at 2 Hz, producing 200 packets/sec) was driven via UDP port 14550. Two k6 WebSocket clients consumed MessagePack broadcasts. Metrics were gathered over 10 consecutive 5-second test runs following a 5-second warmup.

---

## 3. What was measured?
*   **Throughput (msg/s):** The rate of WebSocket messages parsed and consumed.
*   **Latency (ms):** Hardcoded client placeholder; not experimentally measured.
*   **Deployment Footprint (MB):** Static Docker image size.

---

## 4. What was observed?

### Core Throughput & Static Deployment Footprint
Throughput values represent the mean WebSocket messages parsed and consumed per second over 10 runs. Docker sizes represent the static image footprints.

| Framework | Language | Mean (msg/s) | Median (msg/s) | Std Dev | 95th Pct (msg/s) | Docker Size |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **nethttp** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 | **~29 MB** |
| **fiber** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 | **~29 MB** |
| **chi** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 | **~29 MB** |
| **gin** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 | **~29 MB** |
| **echo** | Go | 2384.00 | 2400.00 | 48.00 | 2400.00 | **~29 MB** |
| **uwebsockets** | TypeScript | 1962.88 | 2004.00 | 204.83 | 2158.92 | **~979 MB** |
| **aiohttp** | Python | 1931.56 | 1937.20 | 71.44 | 2030.56 | **~380 MB** |
| **hono** | TypeScript | 1773.72 | 1781.00 | 29.61 | 1809.12 | **~440 MB** |
| **express** | TypeScript | 1772.94 | 1813.20 | 181.01 | 1976.30 | **~440 MB** |
| **sanic** | Python | 1728.72 | 1786.60 | 119.94 | 1840.60 | **~380 MB** |
| **starlette** | Python | 1708.64 | 1735.40 | 130.58 | 1870.28 | **~380 MB** |
| **fastapi** | Python | 1705.64 | 1718.40 | 143.43 | 1873.42 | **~380 MB** |
| **litestar** | Python | 1703.60 | 1762.00 | 144.77 | 1859.66 | **~380 MB** |

---

## 5. What limitations exist?
*   **Latency Metrics:** Absolute end-to-end telemetry transit time was not experimentally measured due to clock isolation. The `1.00` ms latency reported in k6 logs is a mock placeholder. Comparisons between candidates regarding delivery speed are invalid.
*   **Resource Utilization:** Runtime CPU and memory utilization under load were not monitored or captured. Resource efficiency conclusions are limited to static Docker image sizes and code inspections.

---

## 6. What conclusions are supported by the measurements?
*   **Go Candidates:** Saturation of the 2400 msg/s ceiling and small static Docker size (~29 MB) support the selection of Go (e.g., `net/http` or `Chi`) for high-frequency telemetry ingestion gateways resembling the M1 benchmark environment. Performance on specific embedded hardware targets requires independent validation.
*   **Non-Go Candidates:** TypeScript and Python candidates observed lower throughput and larger static footprints. `uWebSockets.js` achieved the highest non-Go throughput (1962.88 msg/s) and `aiohttp` led the Python candidates (1931.56 msg/s).
