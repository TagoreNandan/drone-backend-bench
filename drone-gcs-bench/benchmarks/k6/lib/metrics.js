import { Counter, Rate, Trend } from "k6/metrics";

export const benchmarkFailureRate = new Rate("benchmark_failure_rate");
export const throughputBytesTotal = new Counter("benchmark_throughput_bytes_total");

export const wsMessagesDroppedTotal = new Counter("ws_messages_dropped_total");
export const wsMessageLatencyMs = new Trend("ws_message_latency_ms", true);
export const wsMessagesReceivedTotal = new Counter("ws_messages_received_total");
