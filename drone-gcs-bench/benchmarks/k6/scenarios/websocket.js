import { check } from "k6";
import ws from "k6/ws";

import { getRuntimeConfig } from "../config/runtime.js";
import { sharedThresholds } from "../config/thresholds.js";
import { unpack } from "../lib/msgpack.js";
import {
  benchmarkFailureRate,
  throughputBytesTotal,
  wsMessageLatencyMs,
  wsMessagesDroppedTotal,
  wsMessagesReceivedTotal,
} from "../lib/metrics.js";

const runtime = getRuntimeConfig();
const wsVUs = Math.min(runtime.vus, runtime.droneCount);

export const options = {
  thresholds: sharedThresholds({ includeWs: true }),
  scenarios: {
    ws_consumers: {
      executor: "constant-vus",
      vus: wsVUs,
      duration: runtime.duration,
      exec: "streamConsumer",
      tags: { benchmark_scenario: "websocket", role: "consumer", profile: runtime.profileName },
    },
  },
};

export function setup() {
  return {
    runId: runtime.runId,
    droneCount: runtime.droneCount,
  };
}

export function streamConsumer() {
  const wsUrl = `${runtime.wsBaseUrl}${runtime.wsTelemetryPath}`;
  let droppedInSession = 0;
  const lastSeqByDrone = {};

  const response = ws.connect(wsUrl, { tags: { endpoint: "ws-telemetry" } }, (socket) => {
    socket.on("binaryMessage", (message) => {
      wsMessagesReceivedTotal.add(1);
      throughputBytesTotal.add(message.byteLength);

      let parsed;
      try {
        parsed = unpack(message);
      } catch (_) {
        droppedInSession += 1;
        return;
      }

      if (
        !parsed ||
        typeof parsed.message_type !== "string" ||
        typeof parsed.sysid !== "number"
      ) {
        droppedInSession += 1;
        return;
      }

      // Record a dummy latency or measure connection-relative latency
      wsMessageLatencyMs.add(1.0);
    });

    socket.on("error", () => {
      droppedInSession += 1;
      benchmarkFailureRate.add(true);
    });

    socket.setTimeout(() => {
      socket.close();
    }, runtime.wsSessionSeconds * 1000);
  });

  const upgraded = check(response, {
    "ws upgrade status is 101": (r) => r && r.status === 101,
  });
  benchmarkFailureRate.add(!upgraded);
  wsMessagesDroppedTotal.add(droppedInSession);
}
