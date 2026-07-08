import http from "k6/http";
import { check } from "k6";

import { registrationPayload } from "./telemetry.js";
import { benchmarkFailureRate, throughputBytesTotal } from "./metrics.js";

function chunkArray(items, chunkSize) {
  const chunks = [];
  for (let index = 0; index < items.length; index += chunkSize) {
    chunks.push(items.slice(index, index + chunkSize));
  }
  return chunks;
}

export function registerDrones(baseUrl, droneCount) {
  const registerUrl = `${baseUrl}/api/v1/drones/register`;
  const droneIndexes = Array.from({ length: droneCount }, (_, index) => index);
  const chunks = chunkArray(droneIndexes, 200);

  for (const chunk of chunks) {
    const batchRequests = chunk.map((droneIndex) => {
      const body = JSON.stringify(registrationPayload(droneIndex));
      throughputBytesTotal.add(body.length);
      return [
        "POST",
        registerUrl,
        body,
        {
          headers: { "Content-Type": "application/json" },
          tags: { endpoint: "register", phase: "setup" },
        },
      ];
    });

    const responses = http.batch(batchRequests);
    for (const response of responses) {
      const ok = check(response, {
        "setup register status is 200": (r) => r.status === 200,
      });
      benchmarkFailureRate.add(!ok);
      if (response.body) {
        throughputBytesTotal.add(response.body.length);
      }
    }
  }
}
