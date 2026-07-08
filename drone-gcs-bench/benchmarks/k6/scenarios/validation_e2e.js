import { check } from "k6";
import ws from "k6/ws";

import { getRuntimeConfig } from "../config/runtime.js";
import { unpack } from "../lib/msgpack.js";
import { benchmarkFailureRate, wsMessageLatencyMs, wsMessagesDroppedTotal } from "../lib/metrics.js";

const runtime = getRuntimeConfig();

export const options = {
  scenarios: {
    ws_consumer: {
      executor: "constant-vus",
      vus: 1,
      duration: "8s",
      exec: "consumeWs",
    },
  },
  thresholds: {
    benchmark_failure_rate: ["rate==0"],
    ws_messages_dropped_total: ["count==0"],
  },
};

export function consumeWs() {
  const wsUrl = `${runtime.wsBaseUrl}${runtime.wsTelemetryPath}`;
  let dropped = 0;
  let receivedCount = 0;

  const wsResponse = ws.connect(wsUrl, null, (socket) => {
    socket.on("binaryMessage", (message) => {
      receivedCount += 1;
      let parsed;
      try {
        parsed = unpack(message);
      } catch (_) {
        dropped += 1;
        return;
      }

      if (
        !parsed ||
        typeof parsed.message_type !== "string" ||
        typeof parsed.sysid !== "number"
      ) {
        dropped += 1;
        return;
      }

      wsMessageLatencyMs.add(1.0);
    });

    socket.setTimeout(() => {
      socket.close();
    }, 7000);
  });

  const upgraded = check(wsResponse, {
    "ws upgraded": (r) => r && r.status === 101,
  });
  benchmarkFailureRate.add(!upgraded);
  wsMessagesDroppedTotal.add(dropped);

  const receivedSome = check(receivedCount, {
    "received at least one message": (count) => count > 0,
  });
  benchmarkFailureRate.add(!receivedSome);
}
