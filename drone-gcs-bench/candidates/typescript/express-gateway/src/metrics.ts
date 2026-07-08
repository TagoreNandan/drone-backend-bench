export const DEFAULT_BUCKETS_MS = [
  0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0
];

function formatFloat(value: number): string {
  if (Number.isInteger(value)) {
    return value.toString();
  }
  const str = value.toPrecision(15);
  if (str.includes(".")) {
    return str.replace(/0+$/, "").replace(/\.$/, "");
  }
  return str;
}

function escapeLabelValue(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/"/g, '\\"');
}

class CounterMetric {
  private values = new Map<string, number>();

  constructor(
    public name: string,
    public helpText: string,
    public labelnames: string[] = []
  ) {}

  public inc(value: number = 1.0, labels: string[] = []): void {
    const key = JSON.stringify(labels);
    const current = this.values.get(key) || 0.0;
    this.values.set(key, current + value);
  }

  public render(): string[] {
    const lines = [
      `# HELP ${this.name} ${this.helpText}`,
      `# TYPE ${this.name} counter`
    ];

    const sortedKeys = Array.from(this.values.keys()).sort();
    for (const key of sortedKeys) {
      const labels: string[] = JSON.parse(key);
      const val = this.values.get(key)!;
      const formattedLabels = this.formatLabels(labels);
      lines.push(`${this.name}${formattedLabels} ${formatFloat(val)}`);
    }
    return lines;
  }

  private formatLabels(values: string[]): string {
    if (this.labelnames.length === 0) return "";
    const parts = this.labelnames.map((name, i) => `${name}="${escapeLabelValue(values[i] ?? "")}"`);
    return `{${parts.join(",")}}`;
  }
}

class GaugeMetric {
  private value = 0.0;

  constructor(public name: string, public helpText: string) {}

  public inc(value: number = 1.0): void {
    this.value += value;
  }

  public dec(value: number = 1.0): void {
    this.value -= value;
  }

  public render(): string[] {
    return [
      `# HELP ${this.name} ${this.helpText}`,
      `# TYPE ${this.name} gauge`,
      `${this.name} ${formatFloat(this.value)}`
    ];
  }
}

class HistogramMetric {
  private counts: number[];
  private count = 0;
  private sum = 0.0;

  constructor(
    public name: string,
    public helpText: string,
    public buckets: number[] = DEFAULT_BUCKETS_MS
  ) {
    this.counts = new Array(buckets.length).fill(0);
  }

  public observe(value: number): void {
    this.count++;
    this.sum += value;
    for (let i = 0; i < this.buckets.length; i++) {
      if (value <= this.buckets[i]!) {
        const val = this.counts[i] ?? 0;
        this.counts[i] = val + 1;
        break;
      }
    }
  }

  public render(): string[] {
    const lines = [
      `# HELP ${this.name} ${this.helpText}`,
      `# TYPE ${this.name} histogram`
    ];

    let cumulative = 0;
    for (let i = 0; i < this.buckets.length; i++) {
      cumulative += this.counts[i] ?? 0;
      lines.push(`${this.name}_bucket{le="${formatFloat(this.buckets[i]!)}"} ${cumulative}`);
    }
    lines.push(`${this.name}_bucket{le="+Inf"} ${this.count}`);
    lines.push(`${this.name}_count ${this.count}`);
    lines.push(`${this.name}_sum ${formatFloat(this.sum)}`);
    return lines;
  }
}

export class MetricsRegistry {
  public http_requests_total = new CounterMetric(
    "http_requests_total",
    "Total HTTP requests processed by the service.",
    ["route", "method", "status"]
  );
  public http_request_duration_ms = new HistogramMetric(
    "http_request_duration_ms",
    "HTTP request duration in milliseconds."
  );
  public ws_connections_active = new GaugeMetric(
    "ws_connections_active",
    "Current number of active WebSocket connections."
  );
  public ws_messages_sent_total = new CounterMetric(
    "ws_messages_sent_total",
    "Total WebSocket messages successfully written."
  );
  public ws_messages_dropped_total = new CounterMetric(
    "ws_messages_dropped_total",
    "Total WebSocket messages dropped before delivery."
  );
  public ws_send_latency_ms = new HistogramMetric(
    "ws_send_latency_ms",
    "Latency to write WebSocket messages in milliseconds."
  );
  public telemetry_ingest_total = new CounterMetric(
    "telemetry_ingest_total",
    "Total telemetry events ingested successfully."
  );
  public telemetry_ingest_latency_ms = new HistogramMetric(
    "telemetry_ingest_latency_ms",
    "Telemetry ingestion latency in milliseconds."
  );
  public telemetry_decode_time_ms = new HistogramMetric(
    "telemetry_decode_time_ms",
    "MAVLink telemetry parsing and MessagePack conversion time"
  );

  public recordHttpRequest(route: string, method: string, status: string, durationMs: number): void {
    this.http_requests_total.inc(1.0, [route, method, status]);
    this.http_request_duration_ms.observe(durationMs);
  }

  public recordTelemetryIngest(durationMs: number): void {
    this.telemetry_ingest_total.inc();
    this.telemetry_ingest_latency_ms.observe(durationMs);
  }

  public recordTelemetryDecode(elapsedMs: number): void {
    this.telemetry_decode_time_ms.observe(elapsedMs);
  }

  public recordWsSend(durationMs: number): void {
    this.ws_messages_sent_total.inc();
    this.ws_send_latency_ms.observe(durationMs);
  }

  public recordWsDrop(): void {
    this.ws_messages_dropped_total.inc();
  }

  public render(): string {
    const lines: string[] = [];
    lines.push(...this.http_requests_total.render());
    lines.push(...this.http_request_duration_ms.render());
    lines.push(...this.ws_connections_active.render());
    lines.push(...this.ws_messages_sent_total.render());
    lines.push(...this.ws_messages_dropped_total.render());
    lines.push(...this.ws_send_latency_ms.render());
    lines.push(...this.telemetry_ingest_total.render());
    lines.push(...this.telemetry_ingest_latency_ms.render());
    lines.push(...this.telemetry_decode_time_ms.render());
    return lines.join("\n") + "\n";
  }
}
