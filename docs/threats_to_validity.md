# threats_to_validity.md

This document outlines the limitations, potential biases, and statistical validity constraints of the GCS telemetry bridge benchmark campaign.

---

### **1. Latency Measurement Limitations**
*   **Limitation:** Delivery latency for all WebSocket client runs is recorded as a static `1.0` ms constant.
*   **Explanation:** Because the k6 load generator runs in a separate process space from the background UDP simulator, the client lacks a shared clock or context to correlate the exact transmission time of a UDP packet with its arrival on the WebSocket socket. The latency metrics collected represent a mock placeholder (`wsMessageLatencyMs.add(1.0)`) and should not be used to evaluate framework performance.

### **2. Workload Scale Limitations**
*   **Limitation:** Varying drone scale configurations (`DRONE_COUNT=1`, `DRONE_COUNT=10`, `DRONE_COUNT=100`) do not reflect varying simulator loads.
*   **Explanation:** The shell runner script [`run-profile.sh`](../benchmarks/k6/scripts/run-profile.sh) hardcodes the background simulator settings to `100` drones @ 2Hz whenever the `"websocket"` scenario is selected. Although k6 client properties are configured via environment variables to represent different scales, the physical input load driven to the socket is identical across all runs.

### **3. CPU/Memory Utilization Limitations**
*   **Limitation:** Resource utilization metrics are reported as `N/A`.
*   **Explanation:** There was no container metrics profiling tool active during the benchmark runs, and the custom Node metrics exporter did not integrate process resource handles. CPU and memory footprints could only be assessed qualitatively via static Docker build sizes.

### **4. Docker Runtime Effects**
*   **Limitation:** Host resource allocation and hypervisor settings bias container execution.
*   **Explanation:** Running benchmarks inside Docker Desktop on macOS utilizes a virtualized Linux Kit runtime environment. Storage drivers and socket networking layers incur translation overhead, which may not represent bare-metal execution on physical drone companion computers.

### **5. Language & Runtime Differences**
*   **Limitation:** TS candidates execute using `npx tsx` on-the-fly transpilation, whereas Go candidates run compiled machine binaries.
*   **Explanation:** Running TypeScript code via transpiler wrappers adds runtime compiling threads and development package dependency footprints inside the container, penalizing TS performance relative to pre-bundled JavaScript executions.

### **6. Sequential Execution Bias**
*   **Limitation:** Runs were executed sequentially over a single CPU core schedule.
*   **Explanation:** Host background processes, CPU thermal throttling, or garbage collection spikes in one candidate run could skew results. Mid-campaign Docker daemon outages also forced split-phase execution.

### **7. Statistical Limitations**
*   **Limitation:** The sample size is limited to 10 runs of 5 seconds each.
*   **Explanation:** Short run durations fail to capture long-term heap growth, memory leaks, connection degradation, or socket resource leaks.

### **8. Future Improvements**
*   **Integrated Timestamps:** Include millisecond epoch timestamps inside MAVLink packet payloads or UDP packets so consumer clients can calculate true transit time.
*   **Dynamic Workload Drivers:** Fix `run-profile.sh` to accept dynamic drone counts and load rates from the calling orchestrator.
*   **Resource Profiling:** Integrate `docker stats` capture during the active load window.
