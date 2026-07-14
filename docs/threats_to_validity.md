# GCS Telemetry Bridge Benchmark Threats to Validity

---

## 1. What limitations exist in the benchmark measurements?

### A. Mocked Client Latency Metric
*   **Limitation:** Delivery latency for all WebSocket client runs is recorded as a static `1.0` ms constant.
*   **Explanation:** Because the k6 load generator runs in a separate process space from the background UDP simulator, the client lacks a shared clock or context to correlate the exact transmission time of a UDP packet with its arrival on the WebSocket socket. The latency metrics collected represent a mock placeholder (`wsMessageLatencyMs.add(1.0)`) and must not be interpreted as experimentally measured delivery latency. Comparisons between candidate frameworks on delivery speed are invalid.

### B. Workload Scale Limitations
*   **Limitation:** Varying drone scale configurations (`DRONE_COUNT=1`, `DRONE_COUNT=10`, `DRONE_COUNT=100`) do not reflect varying simulator loads.
*   **Explanation:** The shell runner script [`run-profile.sh`](../benchmarks/k6/scripts/run-profile.sh) hardcodes the background simulator settings to `100` drones @ 2Hz whenever the `"websocket"` scenario is selected. Although k6 client properties are configured via environment variables to represent different scales, the physical input load driven to the socket is identical across all runs.

### C. CPU/Memory Utilization Limitations
*   **Limitation:** Resource utilization metrics under load are reported as `N/A`.
*   **Explanation:** There was no container metrics profiling tool active during the benchmark runs. CPU and runtime memory usage under load was not experimentally measured; static deployment footprints were assessed via Docker image sizes.

### D. Docker Runtime Effects
*   **Limitation:** Host resource allocation and virtualized networking may introduce translation overhead.
*   **Explanation:** Running benchmarks inside Docker Desktop on macOS utilizes a virtualized Linux Kit runtime environment. Storage drivers and socket networking layers may introduce translation overhead, which may not represent bare-metal execution on physical embedded hardware targets.

### E. Language & Runtime Differences
*   **Limitation:** TS candidates execute using `npx tsx` on-the-fly transpilation, whereas Go candidates run compiled machine binaries.
*   **Explanation:** Running TypeScript code via transpiler wrappers may add runtime compiling threads and larger development package dependency footprints inside the container, which may affect TS performance relative to pre-bundled JavaScript executions.

### F. Sequential Execution Bias
*   **Limitation:** Runs were executed sequentially over a single CPU core schedule.
*   **Explanation:** Host background processes, CPU thermal throttling, or garbage collection spikes in one candidate run could introduce minor statistical noise.

### G. Bounded Sample Size
*   **Limitation:** The sample size is limited to 10 runs of 5 seconds each.
*   **Explanation:** Short run durations fail to capture long-term heap growth, memory leaks, connection degradation, or socket resource leaks.

---

## 2. What future work is supported to address these limitations?
*   **Integrated Timestamps:** Include millisecond epoch timestamps inside MAVLink packet payloads or UDP packets so consumer clients can calculate true transit time.
*   **Dynamic Workload Drivers:** Fix `run-profile.sh` to accept dynamic drone counts and load rates from the calling orchestrator.
*   **Resource Profiling:** Integrate `docker stats` capture during the active load window.
