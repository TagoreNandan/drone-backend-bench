package metrics

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
)

func formatFloat(val float64) string {
	return strconv.FormatFloat(val, 'g', 15, 64)
}

func escapeLabelValue(val string) string {
	r := strings.NewReplacer(
		"\\", "\\\\",
		"\n", "\\n",
		"\"", "\\\"",
	)
	return r.Replace(val)
}

type CounterMetric struct {
	mu         sync.Mutex
	name       string
	helpText   string
	labelNames []string
	values     map[string]float64
}

func NewCounter(name, helpText string, labelNames []string) *CounterMetric {
	return &CounterMetric{
		name:       name,
		helpText:   helpText,
		labelNames: labelNames,
		values:     make(map[string]float64),
	}
}

func (c *CounterMetric) Inc(val float64, labels []string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	key := strings.Join(labels, "\x00")
	c.values[key] += val
}

func (c *CounterMetric) Render() []string {
	lines := []string{
		fmt.Sprintf("# HELP %s %s", c.name, c.helpText),
		fmt.Sprintf("# TYPE %s counter", c.name),
	}

	c.mu.Lock()
	keys := make([]string, 0, len(c.values))
	for k := range c.values {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	for _, k := range keys {
		val := c.values[k]
		var labels []string
		if k != "" {
			labels = strings.Split(k, "\x00")
		}
		formattedLabels := c.formatLabels(labels)
		lines = append(lines, fmt.Sprintf("%s%s %s", c.name, formattedLabels, formatFloat(val)))
	}
	c.mu.Unlock()
	return lines
}

func (c *CounterMetric) formatLabels(values []string) string {
	if len(c.labelNames) == 0 {
		return ""
	}
	parts := make([]string, len(c.labelNames))
	for i, name := range c.labelNames {
		val := ""
		if i < len(values) {
			val = values[i]
		}
		parts[i] = fmt.Sprintf(`%s="%s"`, name, escapeLabelValue(val))
	}
	return "{" + strings.Join(parts, ",") + "}"
}

type GaugeMetric struct {
	mu       sync.Mutex
	name     string
	helpText string
	value    float64
}

func NewGauge(name, helpText string) *GaugeMetric {
	return &GaugeMetric{
		name:     name,
		helpText: helpText,
	}
}

func (g *GaugeMetric) Inc(val float64) {
	g.mu.Lock()
	g.value += val
	g.mu.Unlock()
}

func (g *GaugeMetric) Dec(val float64) {
	g.mu.Lock()
	g.value -= val
	g.mu.Unlock()
}

func (g *GaugeMetric) Render() []string {
	g.mu.Lock()
	val := g.value
	g.mu.Unlock()
	return []string{
		fmt.Sprintf("# HELP %s %s", g.name, g.helpText),
		fmt.Sprintf("# TYPE %s gauge", g.name),
		fmt.Sprintf("%s %s", g.name, formatFloat(val)),
	}
}

var DefaultBuckets = []float64{
	0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0,
}

type HistogramMetric struct {
	mu       sync.Mutex
	name     string
	helpText string
	buckets  []float64
	counts   []uint64
	count    uint64
	sum      float64
}

func NewHistogram(name, helpText string) *HistogramMetric {
	return &HistogramMetric{
		name:     name,
		helpText: helpText,
		buckets:  DefaultBuckets,
		counts:   make([]uint64, len(DefaultBuckets)),
	}
}

func (h *HistogramMetric) Observe(val float64) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.count++
	h.sum += val
	for i, b := range h.buckets {
		if val <= b {
			h.counts[i]++
			break
		}
	}
}

func (h *HistogramMetric) Render() []string {
	h.mu.Lock()
	defer h.mu.Unlock()

	lines := []string{
		fmt.Sprintf("# HELP %s %s", h.name, h.helpText),
		fmt.Sprintf("# TYPE %s histogram", h.name),
	}

	var cumulative uint64
	for i, b := range h.buckets {
		cumulative += h.counts[i]
		lines = append(lines, fmt.Sprintf(`%s_bucket{le="%s"} %d`, h.name, formatFloat(b), cumulative))
	}
	lines = append(lines, fmt.Sprintf(`%s_bucket{le="+Inf"} %d`, h.name, h.count))
	lines = append(lines, fmt.Sprintf(`%s_count %d`, h.name, h.count))
	lines = append(lines, fmt.Sprintf(`%s_sum %s`, h.name, formatFloat(h.sum)))
	return lines
}

type MetricsRegistry struct {
	HttpRequestsTotal        *CounterMetric
	HttpRequestDurationMs    *HistogramMetric
	WsConnectionsActive      *GaugeMetric
	WsMessagesSentTotal      *CounterMetric
	WsMessagesDroppedTotal    *CounterMetric
	WsSendLatencyMs          *HistogramMetric
	TelemetryIngestTotal     *CounterMetric
	TelemetryIngestLatencyMs *HistogramMetric
	TelemetryDecodeTimeMs    *HistogramMetric
}

func NewRegistry() *MetricsRegistry {
	return &MetricsRegistry{
		HttpRequestsTotal:        NewCounter("http_requests_total", "Total HTTP requests processed by the service.", []string{"route", "method", "status"}),
		HttpRequestDurationMs:    NewHistogram("http_request_duration_ms", "HTTP request duration in milliseconds."),
		WsConnectionsActive:      NewGauge("ws_connections_active", "Current number of active WebSocket connections."),
		WsMessagesSentTotal:      NewCounter("ws_messages_sent_total", "Total WebSocket messages successfully written.", nil),
		WsMessagesDroppedTotal:    NewCounter("ws_messages_dropped_total", "Total WebSocket messages dropped before delivery.", nil),
		WsSendLatencyMs:          NewHistogram("ws_send_latency_ms", "Latency to write WebSocket messages in milliseconds."),
		TelemetryIngestTotal:     NewCounter("telemetry_ingest_total", "Total telemetry events ingested successfully.", nil),
		TelemetryIngestLatencyMs: NewHistogram("telemetry_ingest_latency_ms", "Telemetry ingestion ingestion latency in milliseconds."),
		TelemetryDecodeTimeMs:    NewHistogram("telemetry_decode_time_ms", "MAVLink message decoding and serialization time in milliseconds."),
	}
}

func (r *MetricsRegistry) RecordHttpRequest(route, method, status string, durationMs float64) {
	r.HttpRequestsTotal.Inc(1.0, []string{route, method, status})
	r.HttpRequestDurationMs.Observe(durationMs)
}

func (r *MetricsRegistry) RecordTelemetryIngest(durationMs float64) {
	r.TelemetryIngestTotal.Inc(1.0, nil)
	r.TelemetryIngestLatencyMs.Observe(durationMs)
}

func (r *MetricsRegistry) RecordTelemetryDecode(durationMs float64) {
	r.TelemetryDecodeTimeMs.Observe(durationMs)
	r.TelemetryIngestTotal.Inc(1.0, nil)
}

func (r *MetricsRegistry) RecordWsSend(durationMs float64) {
	r.WsMessagesSentTotal.Inc(1.0, nil)
	r.WsSendLatencyMs.Observe(durationMs)
}

func (r *MetricsRegistry) RecordWsDrop() {
	r.WsMessagesDroppedTotal.Inc(1.0, nil)
}

func (r *MetricsRegistry) Render() string {
	var lines []string
	lines = append(lines, r.HttpRequestsTotal.Render()...)
	lines = append(lines, r.HttpRequestDurationMs.Render()...)
	lines = append(lines, r.WsConnectionsActive.Render()...)
	lines = append(lines, r.WsMessagesSentTotal.Render()...)
	lines = append(lines, r.WsMessagesDroppedTotal.Render()...)
	lines = append(lines, r.WsSendLatencyMs.Render()...)
	lines = append(lines, r.TelemetryIngestTotal.Render()...)
	lines = append(lines, r.TelemetryIngestLatencyMs.Render()...)
	lines = append(lines, r.TelemetryDecodeTimeMs.Render()...)
	return strings.Join(lines, "\n") + "\n"
}
