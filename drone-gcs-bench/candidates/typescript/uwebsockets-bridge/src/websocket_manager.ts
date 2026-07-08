import { MetricsRegistry } from "./metrics.js";

export class WebSocketManager {
  private connections = new Set<any>();

  constructor(private metrics: MetricsRegistry) {}

  public connect(ws: any) {
    this.connections.add(ws);
    this.metrics.ws_connections_active.inc();
  }

  public disconnect(ws: any) {
    if (this.connections.delete(ws)) {
      this.metrics.ws_connections_active.dec();
    }
  }

  public broadcast(message: Uint8Array) {
    for (const ws of this.connections) {
      const startNs = process.hrtime.bigint();
      try {
        const success = ws.send(message, true);
        if (success) {
          const elapsedNs = process.hrtime.bigint() - startNs;
          const elapsedMs = Number(elapsedNs) / 1_000_000;
          this.metrics.recordWsSend(elapsedMs);
        } else {
          this.metrics.recordWsDrop();
        }
      } catch (err) {
        this.metrics.recordWsDrop();
      }
    }
  }

  public shutdown() {
    for (const ws of this.connections) {
      try {
        ws.close();
      } catch {}
    }
    this.connections.clear();
  }
}
