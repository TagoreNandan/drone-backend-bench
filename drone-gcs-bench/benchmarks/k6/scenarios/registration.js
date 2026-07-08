import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";

import { getRuntimeConfig } from "../config/runtime.js";
import { sharedThresholds } from "../config/thresholds.js";
import { benchmarkFailureRate, throughputBytesTotal } from "../lib/metrics.js";
import { registrationPayload } from "../lib/telemetry.js";

const runtime = getRuntimeConfig();
const registrationRate = Number.parseInt(__ENV.REGISTRATION_RATE || "0", 10) || Math.max(1, Math.floor(runtime.droneCount / 10));

export const options = {
  thresholds: sharedThresholds(),
  scenarios: {
    registration: {
      executor: "constant-arrival-rate",
      rate: registrationRate,
      timeUnit: "1s",
      duration: runtime.duration,
      preAllocatedVUs: runtime.vus,
      maxVUs: Math.max(runtime.vus * 2, runtime.vus + 20),
      exec: "registrationScenario",
      tags: { benchmark_scenario: "registration", profile: runtime.profileName },
    },
  },
};

export function registrationScenario() {
  const iteration = exec.scenario.iterationInTest;
  const droneIndex = iteration % runtime.droneCount;
  const payload = registrationPayload(droneIndex);
  const body = JSON.stringify(payload);
  const response = http.post(`${runtime.baseUrl}${runtime.apiPrefix}/drones/register`, body, {
    headers: { "Content-Type": "application/json" },
    tags: { endpoint: "register" },
  });

  throughputBytesTotal.add(body.length);
  if (response.body) {
    throughputBytesTotal.add(response.body.length);
  }

  const ok = check(response, {
    "register status is 200": (r) => r.status === 200,
    "register returns same drone_id": (r) => r.json("drone_id") === payload.drone_id,
  });
  benchmarkFailureRate.add(!ok);
}
