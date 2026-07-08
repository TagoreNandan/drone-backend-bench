export function sharedThresholds({ includeWs = false } = {}) {
  const thresholds = {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["avg<500", "p(50)<250", "p(95)<1000", "p(99)<2000"],
    benchmark_failure_rate: ["rate<0.01"],
  };
  if (includeWs) {
    thresholds.ws_message_latency_ms = ["avg<1000", "p(50)<500", "p(95)<2000", "p(99)<5000"];
    thresholds.ws_messages_dropped_total = ["count==0"];
  }
  return thresholds;
}
