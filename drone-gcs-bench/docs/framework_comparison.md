# GCS Telemetry Bridge Framework Comparison

This document compares candidate frameworks based on experimental, architectural, and ecosystem evidence collected during the GCS telemetry bridge audit campaign.

---

### **1. Measured Findings (Throughput & Latency)**

*   **Go Candidates (`nethttp`, `fiber`, `chi`, `gin`, `echo`):**
    *   *Throughput:* Consistently saturated the benchmark load ceiling, achieving **2400.00 msg/s** (with the exception of `echo` at 2384.00 msg/s).
    *   *Latency:* Reported baseline value of **1.00 ms** across all runs (reflecting the hardcoded client mock metric).
    *   *Performance Consistency:* Showed 0.00 standard deviation across 10 consecutive test runs (echo showed 48.00 std dev).
*   **TypeScript Candidates (`uwebsockets`, `hono`, `express`):**
    *   *Throughput:* `uwebsockets` achieved **1962.88 msg/s**; `hono` and `express` achieved **~1773 msg/s**.
    *   *Latency:* 1.00 ms (mock baseline).
*   **Python Candidates (`aiohttp`, `sanic`, `starlette`, `fastapi`, `litestar`):**
    *   *Throughput:* `aiohttp` led the class at **1931.56 msg/s**; `sanic` at **1728.72 msg/s**; and `fastapi`/`litestar`/`starlette` grouped around **~1705 msg/s**.
    *   *Latency:* 1.00 ms (mock baseline).

---

### **2. Architectural Findings**

*   **Go Runtimes:**
    *   Statically compiled native binaries copy directly to minimal `alpine` images, producing the lowest container size (**~29MB**).
    *   Execute directly without runtime translation or virtual machine layers.
*   **Python Runtimes:**
    *   Deploy within standard `python-slim` images (**~380MB**).
    *   Execute bytecode via standard ASGI loops (`uvicorn` or python runner).
*   **TypeScript Runtimes:**
    *   Require `node-slim` dependencies, resulting in image sizes of **440MB to 979MB**.
    *   `hono`, `express`, and `uwebsockets` execute TS files via `npx tsx` on-the-fly transpilation inside production containers, increasing CPU compile threads.

---

### **3. Ecosystem Findings**

*   **Python Ecosystem:**
    *   High dialect stability due to the presence of `pymavlink`, the industry standard wrapper for MAVLink integrations.
*   **Go Ecosystem:**
    *   `gomavlib` provides structured, performant bindings, but lacks the decade-long field testing of `pymavlink`.
*   **TypeScript Ecosystem:**
    *   `node-mavlink` introduces dialect translation inconsistencies; standard telemetry parsing maps using camelCase (`data.timeBootMs`), resulting in `undefined` values when targets read snake_case (`data.time_boot_ms`).

---

### **4. Deployment Scenarios & Preferred Selections**

*   **Use Go (`nethttp`, `Chi`, `Echo`) when:**
    *   The bridge runs on constrained companion-computer hardware (e.g., Raspberry Pi) where memory footprint (~29MB) and low CPU utilization are hard gating criteria.
*   **Use Python (`FastAPI`, `aiohttp`) when:**
    *   Development velocity and MAVLink dialect compliance are paramount. FastAPI is preferred for control-plane APIs where auto-generated OpenAPI documentation accelerates dashboard integration.
*   **Use TypeScript (`uWebSockets.js`) when:**
    *   Maintaining a unified, isomorphic codebase with the frontend dashboard is the primary architectural driver.

---

### **5. Research Justification**

1.  **Go Candidates Leading in Resource Efficiency and Throughput:** Statically compiled Go binaries are highly optimized for direct UDP socket reading, bypassing virtual machine layers and runtime interpreters. This results in minimal CPU overhead, maximal throughput, and a negligible Docker image footprint (29MB).
2.  **Developer Experience vs. Ingestion Tradeoff:** Python (FastAPI) provides the best API design ergonomics but suffers from ASGI loop overhead. Go is the ideal candidate for edge/companion computers handling telemetry scrapers, while Python/Node is better suited for cloud-based GCS control plane interfaces where execution latency is not a critical constraint.
3.  **TypeScript Runtime Overhead:** TypeScript deployments exhibit higher storage requirements due to `node-slim` dependencies (up to 979MB). Furthermore, utilizing `npx tsx` for on-the-fly transpilation introduces non-trivial runtime CPU overhead compared to pre-compiled alternatives.

---

### **6. Future Work**

*   **Latency Testing Integration:** Rewrite the telemetry ingest flow to pass transmission timestamps so k6 client VUs can record true delivery latency rather than the static `1.0` ms placeholder.
*   **Workload Scaling Checks:** Adjust the shell runner script to accept dynamic simulator parameters, allowing validation of different drone scales (e.g. 10 to 5000 vehicles).
*   **Alternative Transports:** Build out the MQTT and Pub/Sub (NATS/Redis) adapters to benchmark QoS tradeoffs and edge failover durability.
