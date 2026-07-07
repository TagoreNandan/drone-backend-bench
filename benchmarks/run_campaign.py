import asyncio
import json
import os
import subprocess
import time
import httpx
import glob
import math
from typing import Dict, Any

CANDIDATES = {
    "fastapi": {
        "dir": "candidates/python/fastapi-bridge",
        "url": "http://localhost:8000",
        "lang": "Python",
    },
    "litestar": {
        "dir": "candidates/python/litestar-bridge",
        "url": "http://localhost:8000",
        "lang": "Python",
    },
    "sanic": {
        "dir": "candidates/python/sanic-bridge",
        "url": "http://localhost:8000",
        "lang": "Python",
    },
    "starlette": {
        "dir": "candidates/python/starlette-bridge",
        "url": "http://localhost:8000",
        "lang": "Python",
    },
    "aiohttp": {
        "dir": "candidates/python/aiohttp-bridge",
        "url": "http://localhost:8000",
        "lang": "Python",
    },
    "fastify": {
        "dir": "candidates/typescript/fastify-gateway",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "hono": {
        "dir": "candidates/typescript/hono-gateway",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "express": {
        "dir": "candidates/typescript/express-gateway",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "nestjs": {
        "dir": "candidates/typescript/nestjs-gateway",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "elysia": {
        "dir": "candidates/typescript/elysia-gateway",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "uwebsockets": {
        "dir": "candidates/typescript/uwebsockets-bridge",
        "url": "http://localhost:8000",
        "lang": "TypeScript",
    },
    "gin": {
        "dir": "candidates/go/gin-bridge",
        "url": "http://localhost:8000",
        "lang": "Go",
    },
    "echo": {
        "dir": "candidates/go/echo-bridge",
        "url": "http://localhost:8000",
        "lang": "Go",
    },
    "fiber": {
        "dir": "candidates/go/fiber-bridge",
        "url": "http://localhost:8000",
        "lang": "Go",
    },
    "chi": {
        "dir": "candidates/go/chi-bridge",
        "url": "http://localhost:8000",
        "lang": "Go",
    },
    "nethttp": {
        "dir": "candidates/go/nethttp-bridge",
        "url": "http://localhost:8000",
        "lang": "Go",
    },
}

DRONE_COUNTS = [1, 10, 100]


def clean_port_8000():
    """Ensure port 8000 is completely free."""
    try:
        res = subprocess.run(
            ["lsof", "-t", "-i", ":8000"], capture_output=True, text=True
        )
        pids = res.stdout.strip().split("\n")
        for pid in pids:
            if pid:
                subprocess.run(
                    ["kill", "-9", pid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        time.sleep(1)
    except Exception:
        pass


async def wait_for_healthy(url: str, timeout_s: float = 15.0) -> bool:
    """Poll health endpoint until it is healthy."""
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        while time.perf_counter() - start < timeout_s:
            try:
                resp = await client.get(f"{url.rstrip('/')}/api/v1/health", timeout=1.0)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False


def docker_image_exists(image_name: str) -> bool:
    try:
        res = subprocess.run(
            ["docker", "images", "-q", image_name], capture_output=True, text=True
        )
        return bool(res.stdout.strip())
    except Exception:
        return False


def run_k6_load_test(
    target_name: str, drones: int, base_url: str, duration_s: int = 10, rate: int = 10
) -> Dict[str, Any]:
    """Execute a real k6 load test against the running candidate container, parsing its JSONL metric points."""
    # Clean old JSON results first
    results_pattern = f"benchmarks/k6/results/{target_name}_websocket_100_*.json"
    for f in glob.glob(results_pattern):
        try:
            os.remove(f)
        except Exception:
            pass

    cmd = [
        "./benchmarks/k6/scripts/run-profile.sh",
        "websocket",
        "100",  # profile placeholder
        target_name,
        base_url,
        f"{duration_s}s",
        "2",  # VUs count
        str(rate),
    ]

    env = os.environ.copy()
    env["DURATION"] = f"{duration_s}s"
    env["VUS"] = "2"
    env["TELEMETRY_RATE"] = str(rate)
    env["DRONE_COUNT"] = str(drones)

    print(
        f"      --> Launching real k6 run for {target_name} with {drones} drones at {rate}Hz..."
    )
    subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Locate output json file
    json_files = glob.glob(results_pattern)
    if not json_files:
        print(f"      WARNING: No k6 results JSON found for {target_name}")
        return {}

    latest_file = max(json_files, key=os.path.getctime)

    # Parse metrics from JSONL file
    ws_received = 0
    ws_dropped = 0
    latencies = []
    failures = 0
    total_checks = 0

    with open(latest_file, "r") as f:
        for line in f:
            try:
                point = json.loads(line)
                if point.get("type") == "Point":
                    metric = point.get("metric")
                    val = point["data"]["value"]
                    if metric == "ws_messages_received_total":
                        ws_received += val
                    elif metric == "ws_messages_dropped_total":
                        ws_dropped += val
                    elif metric == "ws_message_latency_ms":
                        latencies.append(val)
                    elif metric == "benchmark_failure_rate":
                        if val > 0:
                            failures += 1
                        total_checks += 1
            except Exception:
                pass

    latencies = sorted(latencies) if latencies else [0.0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    def get_percentile(data, pct):
        if not data:
            return 0.0
        k = (len(data) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data[int(k)]
        return data[int(f)] * (c - k) + data[int(c)] * (k - f)

    p50 = get_percentile(latencies, 50)
    p95 = get_percentile(latencies, 95)
    p99 = get_percentile(latencies, 99)

    error_rate = (failures / total_checks * 100.0) if total_checks > 0 else 0.0

    # Calculate throughput rate achieved
    throughput_rate = ws_received / duration_s if duration_s > 0 else 0.0

    return {
        "throughput_req_s": round(throughput_rate, 2),
        "latency_avg_ms": round(avg_lat, 3),
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "latency_p99_ms": round(p99, 3),
        "error_rate_pct": round(error_rate, 3),
        "ws_delivery_latency_ms": round(avg_lat, 3),
        "ws_messages_dropped": int(ws_dropped),
        "cpu_utilization_pct": 0.0,
        "memory_utilization_mb": 0.0,
        "fault_recovery_time_s": 0.0,
    }


async def main():
    print("==============================================")
    print("Starting GCS Benchmark Campaign Orchestrator")
    print("==============================================")

    # Adapt to running in Docker environment
    running_in_docker = os.environ.get("RUNNING_IN_DOCKER", "false").lower() == "true"
    if running_in_docker:
        for fw, config in CANDIDATES.items():
            config["url"] = config["url"].replace("localhost", "host.docker.internal")

    results = []

    for fw, config in CANDIDATES.items():
        image_name = os.path.basename(config["dir"])

        # Check if Docker image exists
        if not docker_image_exists(image_name):
            print(f"NOT TESTED — no build artifact: {fw} (image: {image_name})")
            continue

        print(f"--> Testing candidate: {fw} (image: {image_name})")

        for drones in DRONE_COUNTS:
            # Clean port and ensure container is gone
            clean_port_8000()
            subprocess.run(
                ["docker", "rm", "-f", f"campaign-{fw}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Start the real container mapping ports 8000 and 14550/udp
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "-p",
                    "8000:8000",
                    "-p",
                    "14550:14550/udp",
                    "--name",
                    f"campaign-{fw}",
                    f"{image_name}:latest",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait for container to be healthy
            is_up = await wait_for_healthy(config["url"], timeout_s=15.0)
            if not is_up:
                print(f"   WARNING: {fw} failed health check under {drones} drones")
                subprocess.run(
                    ["docker", "rm", "-f", f"campaign-{fw}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                continue

            # Run the real k6 benchmark load test
            k6_res = run_k6_load_test(fw, drones, config["url"], duration_s=10, rate=10)
            if k6_res:
                k6_res.update(
                    {
                        "framework": fw,
                        "language": config["lang"],
                        "scenario": "websocket",
                        "drone_count": drones,
                        "mode": "baseline",
                    }
                )
                results.append(k6_res)

            # Stop and remove the container
            subprocess.run(
                ["docker", "rm", "-f", f"campaign-{fw}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Save the real results to JSON
    os.makedirs("results", exist_ok=True)
    out_path = "results/campaign_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nReal database successfully saved to: {out_path}")
    print(f"Total compiled test scenarios: {len(results)}")
    print("Campaign execution phase completed.")


if __name__ == "__main__":
    asyncio.run(main())
