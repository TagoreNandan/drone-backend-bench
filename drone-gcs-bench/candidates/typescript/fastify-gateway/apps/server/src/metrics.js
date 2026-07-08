export const DEFAULT_BUCKETS_MS = [
    0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0
];
function formatFloat(value) {
    if (Number.isInteger(value)) {
        return value.toString();
    }
    const str = value.toPrecision(15);
    if (str.includes(".")) {
        return str.replace(/0+$/, "").replace(/\.$/, "");
    }
    return str;
}
function escapeLabelValue(value) {
    return value
        .replace(/\\/g, "\\\\")
        .replace(/\n/g, "\\n")
        .replace(/"/g, '\\"');
}
class CounterMetric {
    name;
    helpText;
    labelnames;
    values = new Map();
    constructor(name, helpText, labelnames = []) {
        this.name = name;
        this.helpText = helpText;
        this.labelnames = labelnames;
    }
    inc(value = 1.0, labels = []) {
        const key = JSON.stringify(labels);
        const current = this.values.get(key) || 0.0;
        this.values.set(key, current + value);
    }
    render() {
        const lines = [
            `# HELP ${this.name} ${this.helpText}`,
            `# TYPE ${this.name} counter`
        ];
        const sortedKeys = Array.from(this.values.keys()).sort();
        for (const key of sortedKeys) {
            const labels = JSON.parse(key);
            const val = this.values.get(key);
            const formattedLabels = this.formatLabels(labels);
            lines.push(`${this.name}${formattedLabels} ${formatFloat(val)}`);
        }
        return lines;
    }
    formatLabels(values) {
        if (this.labelnames.length === 0)
            return "";
        const parts = this.labelnames.map((name, i) => `${name}="${escapeLabelValue(values[i] ?? "")}"`);
        return `{${parts.join(",")}}`;
    }
}
class GaugeMetric {
    name;
    helpText;
    value = 0.0;
    constructor(name, helpText) {
        this.name = name;
        this.helpText = helpText;
    }
    inc(value = 1.0) {
        this.value += value;
    }
    dec(value = 1.0) {
        this.value -= value;
    }
    render() {
        return [
            `# HELP ${this.name} ${this.helpText}`,
            `# TYPE ${this.name} gauge`,
            `${this.name} ${formatFloat(this.value)}`
        ];
    }
}
class HistogramMetric {
    name;
    helpText;
    buckets;
    counts;
    count = 0;
    sum = 0.0;
    constructor(name, helpText, buckets = DEFAULT_BUCKETS_MS) {
        this.name = name;
        this.helpText = helpText;
        this.buckets = buckets;
        this.counts = new Array(buckets.length).fill(0);
    }
    observe(value) {
        this.count++;
        this.sum += value;
        for (let i = 0; i < this.buckets.length; i++) {
            if (value <= this.buckets[i]) {
                const val = this.counts[i] ?? 0;
                this.counts[i] = val + 1;
                break;
            }
        }
    }
    render() {
        const lines = [
            `# HELP ${this.name} ${this.helpText}`,
            `# TYPE ${this.name} histogram`
        ];
        let cumulative = 0;
        for (let i = 0; i < this.buckets.length; i++) {
            cumulative += this.counts[i] ?? 0;
            lines.push(`${this.name}_bucket{le="${formatFloat(this.buckets[i])}"} ${cumulative}`);
        }
        lines.push(`${this.name}_bucket{le="+Inf"} ${this.count}`);
        lines.push(`${this.name}_count ${this.count}`);
        lines.push(`${this.name}_sum ${formatFloat(this.sum)}`);
        return lines;
    }
}
export class MetricsRegistry {
    http_requests_total = new CounterMetric("http_requests_total", "Total HTTP requests processed by the service.", ["route", "method", "status"]);
    http_request_duration_ms = new HistogramMetric("http_request_duration_ms", "HTTP request duration in milliseconds.");
    ws_connections_active = new GaugeMetric("ws_connections_active", "Current number of active WebSocket connections.");
    ws_messages_sent_total = new CounterMetric("ws_messages_sent_total", "Total WebSocket messages successfully written.");
    ws_messages_dropped_total = new CounterMetric("ws_messages_dropped_total", "Total WebSocket messages dropped before delivery.");
    ws_send_latency_ms = new HistogramMetric("ws_send_latency_ms", "Latency to write WebSocket messages in milliseconds.");
    telemetry_ingest_total = new CounterMetric("telemetry_ingest_total", "Total telemetry events ingested successfully.");
    telemetry_ingest_latency_ms = new HistogramMetric("telemetry_ingest_latency_ms", "Telemetry ingestion latency in milliseconds.");
    recordHttpRequest(route, method, status, durationMs) {
        this.http_requests_total.inc(1.0, [route, method, status]);
        this.http_request_duration_ms.observe(durationMs);
    }
    recordTelemetryIngest(durationMs) {
        this.telemetry_ingest_total.inc();
        this.telemetry_ingest_latency_ms.observe(durationMs);
    }
    recordWsSend(durationMs) {
        this.ws_messages_sent_total.inc();
        this.ws_send_latency_ms.observe(durationMs);
    }
    recordWsDrop() {
        this.ws_messages_dropped_total.inc();
    }
    render() {
        const lines = [];
        lines.push(...this.http_requests_total.render());
        lines.push(...this.http_request_duration_ms.render());
        lines.push(...this.ws_connections_active.render());
        lines.push(...this.ws_messages_sent_total.render());
        lines.push(...this.ws_messages_dropped_total.render());
        lines.push(...this.ws_send_latency_ms.render());
        lines.push(...this.telemetry_ingest_total.render());
        lines.push(...this.telemetry_ingest_latency_ms.render());
        return lines.join("\n") + "\n";
    }
}
