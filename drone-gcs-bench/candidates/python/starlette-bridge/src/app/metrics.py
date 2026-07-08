"""Minimal Prometheus exposition for the GCS benchmark candidate."""

from __future__ import annotations

import threading
from collections import defaultdict


DEFAULT_BUCKETS_MS = (
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
)


def _escape_label_value(value: str) -> str:
    return value.replace("\\", r"\\").replace("\n", r"\n").replace('"', r'\"')


def _format_labels(labelnames: tuple[str, ...], values: tuple[str, ...]) -> str:
    if not labelnames:
        return ""
    parts = [f'{name}="{_escape_label_value(value)}"' for name, value in zip(labelnames, values, strict=True)]
    return "{" + ",".join(parts) + "}"


class CounterMetric:
    def __init__(self, name: str, help_text: str, labelnames: tuple[str, ...] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.labelnames = labelnames
        self._lock = threading.Lock()
        self._values: dict[tuple[str, ...], float] = defaultdict(float)

    def inc(self, value: float = 1.0, labels: tuple[str, ...] = ()) -> None:
        with self._lock:
            self._values[labels] += value

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        with self._lock:
            for labels, value in sorted(self._values.items()):
                lines.append(f"{self.name}{_format_labels(self.labelnames, labels)} {format(value, '.15g')}")
        return lines


class GaugeMetric:
    def __init__(self, name: str, help_text: str) -> None:
        self.name = name
        self.help_text = help_text
        self._lock = threading.Lock()
        self._value = 0.0

    def inc(self, value: float = 1.0) -> None:
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0) -> None:
        with self._lock:
            self._value -= value

    def render(self) -> list[str]:
        with self._lock:
            val = self._value
        return [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {format(val, '.15g')}",
        ]


class HistogramMetric:
    def __init__(self, name: str, help_text: str, buckets: tuple[float, ...] = DEFAULT_BUCKETS_MS) -> None:
        self.name = name
        self.help_text = help_text
        self.buckets = buckets
        self._lock = threading.Lock()
        self._counts = [0] * len(buckets)
        self._count = 0
        self._sum = 0.0

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value
            for idx, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._counts[idx] += 1
                    break

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} histogram"]
        with self._lock:
            cumulative = 0
            for idx, bucket in enumerate(self.buckets):
                cumulative += self._counts[idx]
                lines.append(f'{self.name}_bucket{{le="{format(bucket, ".15g")}"}} {cumulative}')
            lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._count}')
            lines.append(f"{self.name}_count {self._count}")
            lines.append(f"{self.name}_sum {format(self._sum, '.15g')}")
        return lines


class MetricsRegistry:
    def __init__(self) -> None:
        self.http_requests_total = CounterMetric(
            "http_requests_total",
            "Total HTTP requests processed by the service.",
            labelnames=("route", "method", "status"),
        )
        self.http_request_duration_ms = HistogramMetric(
            "http_request_duration_ms", "HTTP request duration in milliseconds."
        )
        self.ws_connections_active = GaugeMetric(
            "ws_connections_active", "Current number of active WebSocket connections."
        )
        self.ws_messages_sent_total = CounterMetric(
            "ws_messages_sent_total", "Total WebSocket messages successfully written."
        )
        self.ws_messages_dropped_total = CounterMetric(
            "ws_messages_dropped_total", "Total WebSocket messages dropped before delivery."
        )
        self.ws_send_latency_ms = HistogramMetric(
            "ws_send_latency_ms", "Latency to write WebSocket messages in milliseconds."
        )
        self.telemetry_ingest_total = CounterMetric(
            "telemetry_ingest_total", "Total telemetry events ingested successfully."
        )
        self.telemetry_ingest_latency_ms = HistogramMetric(
            "telemetry_ingest_latency_ms", "Telemetry ingestion latency in milliseconds."
        )
        self.telemetry_decode_time_ms = HistogramMetric(
            "telemetry_decode_time_ms", "MAVLink message decoding and serialization time in milliseconds."
        )

    def record_http_request(self, route: str, method: str, status: str, duration_ms: float) -> None:
        self.http_requests_total.inc(1.0, (route, method, status))
        self.http_request_duration_ms.observe(duration_ms)

    def record_telemetry_ingest(self, duration_ms: float) -> None:
        self.telemetry_ingest_total.inc()
        self.telemetry_ingest_latency_ms.observe(duration_ms)

    def record_telemetry_decode(self, duration_ms: float) -> None:
        self.telemetry_decode_time_ms.observe(duration_ms)
        self.telemetry_ingest_total.inc()

    def record_ws_send(self, duration_ms: float) -> None:
        self.ws_messages_sent_total.inc()
        self.ws_send_latency_ms.observe(duration_ms)

    def record_ws_drop(self) -> None:
        self.ws_messages_dropped_total.inc()

    def render(self) -> str:
        lines: list[str] = []
        lines.extend(self.http_requests_total.render())
        lines.extend(self.http_request_duration_ms.render())
        lines.extend(self.ws_connections_active.render())
        lines.extend(self.ws_messages_sent_total.render())
        lines.extend(self.ws_messages_dropped_total.render())
        lines.extend(self.ws_send_latency_ms.render())
        lines.extend(self.telemetry_ingest_total.render())
        lines.extend(self.telemetry_ingest_latency_ms.render())
        lines.extend(self.telemetry_decode_time_ms.render())
        return "\n".join(lines) + "\n"
