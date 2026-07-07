# GCS Telemetry Bridge Benchmark Methodology

This methodology document outlines the evaluation protocols applied to the 13 compliant candidates, categorizing them into experimental benchmarks, architectural inspections, ecosystem evaluations, and qualitative analyses.

---

### **1. Experimental Benchmarks**

The experimental benchmarks measure raw execution throughput and connection stability on a live, containerized stack. 

#### **A. Evaluated Parameters**
*   **Concurrent connections sustained**
*   **Binary vs JSON payload throughput**
*   **Backpressure handling (verification of drops)**

#### **B. Toolchain & Test Rig Setup**
1.  **Workload Generator:** A python script ([`mavlink_sim.py`](../benchmarks/k6/scripts/mavlink_sim.py)) driving simulated telemetry for 100 drones at 2Hz (yielding a baseline stream of 200 packets/sec).
2.  **Telemetry Bridge (Docker):** Detached container instances listening on UDP port `14550/udp` and broadcasting binary MessagePack to a WebSocket endpoint.
3.  **Load Client (k6):** 2 Virtual Users (VUs) consuming WebSocket frames and verifying binary unpacking integrity.

#### **C. Execution Sequence**
1.  Verify host port `8000` is clear.
2.  Launch detached container:
    ```bash
    docker run -d -p 8000:8000 -p 14550:14550/udp --name bench-<fw> <image>:latest
    ```
3.  Poll health endpoints (`/health` or `/api/v1/health`) for up to 15 seconds.
4.  Run a 5-second warmup load test to cached code path execution.
5.  Execute 10 consecutive 5-second test runs, writing raw logs to separate JSON files.
6.  Stop and clean container instances.

---

### **2. Architectural Inspections**

Architectural audits inspect source files and build configurations to verify system properties.

#### **A. Evaluated Parameters**
*   **Memory footprint under load** (analyzed via base runtime environment sizes).
*   **Binary size / deployment footprint** (derived from local `docker images` size outputs).
*   **Backpressure queue configurations** (audited to verify ring-buffer queue ceilings of 2048).
*   **Exposed ports** (audited in candidate Dockerfiles).

---

### **3. Ecosystem Evaluations**

Ecosystem reviews assess the libraries and drivers available in each runtime ecosystem.

#### **A. Evaluated Parameters**
*   **MAVLink/MAVSDK library maturity** (reviewing `pymavlink`, `gomavlib`, and `node-mavlink` implementations).
*   **Time-series DB driver quality** (evaluating driver connection pool standards for QuestDB/TimescaleDB).
*   **Framework-native pub/sub support** (evaluating native client modules for Redis, NATS, and Kafka).
*   **MQTT client library maturity** (assessing Paho-MQTT and `mqtt.js` libraries).

---

### **4. Qualitative Analysis**

Qualitative metrics grade implementation ergonomics and maintainability.

#### **A. Evaluated Parameters**
*   **Test / mocking ergonomics** (auditing testing suite setups).
*   **MQTT broker integration overhead** (evaluating complexity of brokered topologies).
