# GCS Telemetry Bridge Framework Comparison

---

## 1. What was benchmarked?
Thirteen candidate frameworks across three language ecosystems (Go, TypeScript, Python) executing a telemetry bridge (UDP ingestion, MessagePack serialization, WebSocket broadcast).

---

## 2. How was it benchmarked?
Each candidate ran sequentially inside isolated Docker containers on an Apple M1 macOS host, handling a simulated load of 100 drones at 2 Hz (200 packets/sec) over UDP port 14550. Two k6 clients consumed WebSocket frames. Tests consisted of 10 consecutive 5-second test runs following a 5-second warmup.

---

## 3. What was measured?
*   **Throughput (msg/s):** Messages parsed and consumed at the clients.
*   **Static Deployment Footprint (MB):** Storage size of compiled candidate containers.
*   *Note: Runtime memory usage, CPU load, and transit latency were not experimentally measured (the 1.00 ms latency is a hardcoded placeholder).*

---

## 4. What was observed?
*   **Throughput Performance:** Go candidates consistently reached the load ceiling of **2400.00 msg/s** (with the exception of `echo` at 2384.00 msg/s). TypeScript's `uwebsockets` achieved **1962.88 msg/s**, while standard TS candidates (`hono`, `express`) achieved **~1773 msg/s**. Python's `aiohttp` led the class at **1931.56 msg/s**, and `fastapi`/`litestar`/`starlette` grouped around **~1705 msg/s**.
*   **Deployment Footprints:** Go candidates compile to native binaries, yielding Docker sizes of **~29MB** (the smallest in the audit). Python candidates deploy in **~380MB** slim images. TypeScript candidates require Node dependencies, resulting in image sizes of **440MB to 979MB**.
*   **Ecosystem Compatibility:** Python benefits from the mature and standard `pymavlink` parser. Go's `gomavlib` is performant but less field-tested. TypeScript's `node-mavlink` exhibited camelCase translation inconsistencies (`timeBootMs` vs snake_case `time_boot_ms`), which can lead to parsing errors.

---

## 5. What limitations exist?
*   **Mock Latency:** End-to-end telemetry transit time was not experimentally measured due to isolated clock spaces. The `1.00` ms value is a mock placeholder and must not be interpreted as actual delivery latency.
*   **Static Resource Assessment:** Runtime CPU and memory utilization under load were not measured. Evaluation is limited to static Docker image sizes and code inspections.

---

## 6. What conclusions are supported by the measurements?
*   **Go Candidates:** Saturation of the 2400 msg/s ceiling and small static Docker size (~29 MB) support the selection of Go (e.g., `net/http` or `Chi`) for high-frequency telemetry ingestion gateways resembling the M1 benchmark environment. Performance on specific embedded hardware targets requires independent validation.
*   **Python Candidates:** FastAPI provides robust developer ergonomics but may introduce ASGI event loop overhead. It is preferred for cloud-based control planes where throughput is not the primary gating constraint.
*   **TypeScript Candidates:** TypeScript provides isomorphic front-back data model sharing. `uWebSockets.js` is preferred for WebSocket broadcast gateways under tested environments when TS alignment is the primary criteria.
