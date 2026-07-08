# GCS Telemetry Bridge Benchmark Report
## Execution Date: July 3, 2026

### **1. Executive Summary**
This report contains the performance evaluation of 13 candidate framework implementations retrofitted to decode raw MAVLink telemetry packets over UDP, encode them into binary MessagePack frames, and broadcast them to active WebSocket subscribers.

### **2. Core Throughput Results**
Throughput values represent the mean WebSocket messages parsed and consumed per second over 10 consecutive runs:

| Framework | Language | Mean (msg/s) | Median (msg/s) | Std Dev | 95th Pct (msg/s) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **nethttp** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 |
| **fiber** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 |
| **chi** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 |
| **gin** | Go | 2400.00 | 2400.00 | 0.00 | 2400.00 |
| **echo** | Go | 2384.00 | 2400.00 | 48.00 | 2400.00 |
| **uwebsockets** | TypeScript | 1962.88 | 2004.00 | 204.83 | 2158.92 |
| **aiohttp** | Python | 1931.56 | 1937.20 | 71.44 | 2030.56 |
| **hono** | TypeScript | 1773.72 | 1781.00 | 29.61 | 1809.12 |
| **express** | TypeScript | 1772.94 | 1813.20 | 181.01 | 1976.30 |
| **sanic** | Python | 1728.72 | 1786.60 | 119.94 | 1840.60 |
| **starlette** | Python | 1708.64 | 1735.40 | 130.58 | 1870.28 |
| **fastapi** | Python | 1705.64 | 1718.40 | 143.43 | 1873.42 |
| **litestar** | Python | 1703.60 | 1762.00 | 144.77 | 1859.66 |

### **3. Latency Metrics**
Due to k6's isolation from the UDP simulator process, absolute telemetry transit time was not measured. The k6 consumer script hardcoded a static delivery check of `1.0` ms for all candidates:
*   **Mean/Median Latency:** 1.00 ms (all candidates)
*   **Standard Deviation:** 0.00 ms (all candidates)

### **4. Resource Consumption Overview**
Process CPU and memory metrics are not captured in raw k6 logs. However, the Docker image sizes represent the physical deployment footprints:
*   **Go images:** ~29 MB (extremely lightweight)
*   **Python images:** ~380 MB (moderate footprint)
*   **TypeScript images:** ~440 MB to 979 MB (heavy footprint)
