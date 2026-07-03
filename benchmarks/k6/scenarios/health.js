import http from "k6/http";
import { check, sleep } from "k6";

import { getRuntimeConfig } from "../config/runtime.js";
import { sharedThresholds } from "../config/thresholds.js";
import { benchmarkFailureRate, throughputBytesTotal } from "../lib/metrics.js";

const runtime = getRuntimeConfig();

export const options = {
  thresholds: sharedThresholds(),
  scenarios: {
    health: {
      executor: "constant-vus",
      vus: runtime.vus,
      duration: runtime.duration,
      exec: "healthScenario",
      tags: { benchmark_scenario: "health", profile: runtime.profileName },
    },
  },
};

export function healthScenario() {
  const response = http.get(`${runtime.baseUrl}${runtime.apiPrefix}/health`, {
    tags: { endpoint: "health" },
  });
  const ok = check(response, {
    "health status is 200": (r) => r.status === 200,
    "health payload status is ok": (r) => r.json("status") === "ok",
  });

  benchmarkFailureRate.add(!ok);
  if (response.body) {
    throughputBytesTotal.add(response.body.length);
  }
  sleep(1);
}
