# GCS Telemetry Bridge Benchmark Specification
## Reference Identifier: `BENCHMARK_SPEC-v1.0`

This document defines the frozen specifications for the Ground Control Station (GCS) telemetry bridge load testing campaign. All measurements, configurations, and results must adhere to these criteria.

---

### **1. Host System & Runtime Environment**

*   **Host Hardware:** Apple Mac mini / MacBook (2020)
*   **CPU:** Apple M1 (8 Cores, 4 Performance, 4 Efficiency)
*   **RAM:** 8 GB LPDDR4X (unified memory, 8589934592 bytes)
*   **Operating System:** macOS (Product Version 26.2, Build 25C56)
*   **Kernel:** Darwin Zoro-Mac.local 25.2.0 Darwin Kernel Version 25.2.0: Tue Nov 18 21:09:55 PST 2025; root:xnu-12377.61.12~1/RELEASE_ARM64_T8103 arm64
*   **Docker Engine Version:** 28.1.1, build 4eba377
*   **Node.js Version:** v20.17.0
*   **Bun Version:** 1.2.21
*   **Python Version:** 3.13.13
*   **Go Version:** go1.25.6 darwin/arm64
*   **Package Managers:**
    *   `npm`: 10.8.2
    *   `bun`: 1.2.21 (used for Bun candidate dependency resolution)

---

### **2. Benchmark Workload Configuration**

*   **Test Runner:** k6 load testing tool (`constant-vus` executor scenario)
*   **Benchmark Run Duration:** 10 seconds per scenario
*   **Warmup Duration:** 0 seconds (direct constant load)
*   **Number of Runs:** 1 run per candidate per drone count configuration
*   **Telemetry Generation Rate:** 10 Hz (10 telemetry packets/second per drone)
*   **Evaluated Drone Counts:** 1, 10, and 100 drones
*   **Concurrent WebSocket Clients:** 2 Virtual Users (VUs) subscribing constantly to the WebSocket telemetry feed

---

### **3. Collected Metrics Specification**

The following performance metrics are extracted from k6 JSONL streaming logs and Prometheus outputs:

1.  **`throughput_req_s`:** Achieved telemetry messages broadcast and consumed per second over the WebSocket stream.
2.  **`latency_avg_ms`:** Average time (in milliseconds) from MAVLink UDP packet arrival to the WebSocket client receipt.
3.  **`latency_p50_ms`:** 50th percentile (median) message delivery latency.
4.  **`latency_p95_ms`:** 95th percentile message delivery latency.
5.  **`latency_p99_ms`:** 99th percentile message delivery latency.
6.  **`error_rate_pct`:** Percentage of failed WebSocket requests or connection drops.
7.  **`ws_messages_dropped`:** Total number of corrupted, incomplete, or dropped WebSocket frames.
