# GCS Benchmark Telemetry Workload Layer

This directory contains the deterministic telemetry workload generation, recording, and replay infrastructure. It drives the comparative GCS backend framework benchmarks under repeatable, identical flight scenarios and drone count distributions.

---

## 1. Architectural Overview

The workload layer decouples flight simulation/packet generation from GCS ingestion and database testing by using a standardized intermediate replay format.

```text
+-----------------------+              +-----------------------+
|  Synthetic Generator  |  --[UDP]-->  |  Telemetry Recorder   |
| (pymavlink/scenarios) |  (MAVLink)   |   (state caching)     |
+-----------------------+              +-----------------------+
                                                   |
                                             [JSON Lines]
                                                   v
+-----------------------+              +-----------------------+
|   GCS Target Server   |  <--[HTTP]-  |     Replay Engine     |
| (FastAPI, net/http)   |   (POST)     |   (httpx/asyncio)     |
+-----------------------+              +-----------------------+
```

1. **Synthetic Generator**: Computes drone trajectories deterministically using mathematical flight equations, packing coordinates, yaw/heading, altitude, and battery metrics into standard binary MAVLink message frames (`HEARTBEAT`, `ATTITUDE`, `GLOBAL_POSITION_INT`, `SYS_STATUS`) streamed over UDP.
2. **Telemetry Recorder**: Binds to the target UDP socket, caches incoming MAVLink frames per drone ID to construct a fused flight state, and writes sequential JSON envelopes to a `.jsonl` recording file.
3. **Replay Engine**: Reads the `.jsonl` file and replays telemetry requests using high-performance asynchronous HTTP POST requests, preserving the exact relative timestamp offsets and supporting variable speed rates.

---

## 2. Replay Format Specification

The telemetry is recorded in a canonical JSON Lines format where each line represents a single `TelemetryEnvelope` conforming to the GCS OpenAPI schema contract.

### Schema Details
Each JSON Line contains:
- `run_id` (string): The identifier of the recording run.
- `drone_id` (string): Standardized ID mapped from MAVLink IDs: `drone-{sysid + (compid - 1)*250:04d}`.
- `seq` (integer): Monotonically increasing sequence index starting at `0` per drone.
- `timestamp` (integer): Epoch timestamp of receipt in milliseconds.
- `payload` (object):
  - `lat` (float): Latitude in degrees.
  - `lon` (float): Longitude in degrees.
  - `alt` (float): Altitude above sea level in meters.
  - `roll` (float): Roll angle in radians.
  - `pitch` (float): Pitch angle in radians.
  - `yaw` (float): Yaw heading angle in radians.
  - `battery` (integer): Battery percentage remaining (`0` to `100`).
  - `mode` (string): Flight mode (e.g. `HOVER`, `GUIDED`, `AUTO`, `LAND`, `LOITER`).

### Example Record
```json
{
  "run_id": "run-1783038621",
  "drone_id": "drone-0001",
  "seq": 42,
  "timestamp": 1783038625807,
  "payload": {
    "lat": 47.376855,
    "lon": 8.5418989,
    "alt": 410.0,
    "roll": -0.08726646,
    "pitch": 0.03490658,
    "yaw": 1.57079637,
    "battery": 92,
    "mode": "GUIDED"
  }
}
```

---

## 3. Flight Scenarios

All scenario equations are defined inside [scenarios.py](file:///Users/somespecies/drone-gcs-bench/benchmarks/workload/scenarios.py) and represent mathematical functions of time $t$ to ensure complete reproducibility:

- **Hover**: Stationary positioning, standard battery discharge, stabilizer noise.
- **Straight Flight**: Drones fly North at 5 m/s.
- **Waypoint Mission**: Drones fly a closed rectangle path (50m x 50m) at 6 m/s, banking and updating headings at turning thresholds.
- **Circular Orbit**: Drones fly in a circle of 20m radius at $0.2$ rad/s.
- **Figure-Eight**: Coordinates follow a Lemniscate of Bernoulli trajectory.
- **Battery Drain**: Faster battery discharge. When battery drops below 20%, flight mode changes to `LAND` and altitude descends to ground.
- **GPS Drift**: Adds a sinusoidal random walk noise to simulated GPS coordinates.
- **Telemetry Burst**: Buffer transmission events and dump them in high-rate bursts every 500ms.
- **Multi-Drone Swarm**: Drones move together as a flock formation while maintaining safe grid offsets.

---

## 4. Configuration Guide

### MAVLink Synthetic Generator (`generator.py`)
- `--seed`: Deterministic pseudo-random seed (default: `42`).
- `--drones`: Spawns `N` drones (`1`, `10`, `100`, `500`, `1000`).
- `--rate`: Update frequency in Hz (`1.0`, `5.0`, `10.0`, `20.0`).
- `--duration`: Flight duration in seconds.
- `--scenario`: Flight path pattern name.
- `--jitter`: Max simulated network jitter delay in seconds.
- `--loss`: Simulated packet loss probability (`0.0` to `1.0`).

### Telemetry Recorder (`recorder.py`)
- `--listen-host`: UDP listening address (default: `0.0.0.0`).
- `--listen-port`: UDP port to bind (default: `14550`).
- `--output`: Recording path (default: `recording.jsonl`).
- `--run-id`: Identifier for target run envelopes.

### Replay Engine (`replay.py`)
- `--input`: Source recording file.
- `--base-url`: GCS server target host.
- `--speed`: Speed factor multiplier (`0.5`, `1.0`, `2.0`, or `0.0` for maximum speed).
- `--concurrency`: Limit on simultaneous connections.

---

## 5. Docker Compose Integration

The workload layer is integrated via a dedicated compose stack inside this directory. To launch the workload stack:

```bash
# Build the Docker images
docker compose build

# Start recording a simulated flight scenario
docker compose up -d workload-recorder workload-generator

# Replay a recorded file to a running GCS target container
docker compose run --rm workload-replay --base-url http://fastapi-reference:8000
```
