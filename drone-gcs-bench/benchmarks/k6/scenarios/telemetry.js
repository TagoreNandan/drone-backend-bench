import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";

import { getRuntimeConfig } from "../config/runtime.js";
import { sharedThresholds } from "../config/thresholds.js";
import { registerDrones } from "../lib/bootstrap.js";
import { benchmarkFailureRate, throughputBytesTotal } from "../lib/metrics.js";
import { telemetryEnvelope } from "../lib/telemetry.js";

const runtime = getRuntimeConfig();
const telemetryRate = runtime.droneCount * runtime.telemetryRate;

export const options = {
  thresholds: sharedThresholds(),
  scenarios: {
    telemetry: {
      executor: "constant-arrival-rate",
      rate: telemetryRate,
      timeUnit: "1s",
      duration: runtime.duration,
      preAllocatedVUs: runtime.vus,
      maxVUs: Math.max(runtime.vus * 4, runtime.vus + 50),
      exec: "telemetryScenario",
      tags: { benchmark_scenario: "telemetry", profile: runtime.profileName },
    },
  },
};

export function setup() {
  if (runtime.registerDrones) {
    registerDrones(runtime.baseUrl, runtime.droneCount);
  }
  return {
    runId: runtime.runId,
    droneCount: runtime.droneCount,
  };
}

export function telemetryScenario(state) {
  const iteration = exec.scenario.iterationInTest;
  const droneIndex = iteration % state.droneCount;
  const seq = iteration + 1;

  const telemetry = telemetryEnvelope({
    runId: state.runId,
    droneIndex,
    seq,
  });

  const body = JSON.stringify(telemetry);
  const response = http.post(`${runtime.baseUrl}${runtime.apiPrefix}/telemetry`, body, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "telemetry" },
  });

  throughputBytesTotal.add(body.length);
  if (response.body) {
    throughputBytesTotal.add(response.body.length);
  }

  const ok = check(response, {
    "telemetry status is 200": (r) => r.status === 200,
    "telemetry response is ok": (r) => r.json("status") === "ok",
  });
  benchmarkFailureRate.add(!ok);
}
