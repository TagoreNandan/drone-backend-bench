import { WebSocket } from "ws";
import { MetricsRegistry } from "./metrics.js";

export class WebSocketConnection {
  public queue: (string | Uint8Array)[] = [];
  public sending = false;

  constructor(
    public id: number,
    public socket: WebSocket,
    private metrics: MetricsRegistry,
    private onDisconnect: (id: number) => void
  ) {}

  public enqueue(message: string | Uint8Array) {
    if (this.queue.length >= 2048) {
      this.metrics.recordWsDrop();
      return;
    }
    this.queue.push(message);
    this.startSending();
  }

  private async startSending() {
    if (this.sending) return;
    this.sending = true;
    try {
      while (this.queue.length > 0) {
        const message = this.queue.shift()!;
        const startNs = process.hrtime.bigint();
        try {
          await this.sendAsync(message);
          const elapsedNs = process.hrtime.bigint() - startNs;
          const elapsedMs = Number(elapsedNs) / 1_000_000;
          this.metrics.recordWsSend(elapsedMs);
        } catch (err) {
          this.metrics.recordWsDrop();
          this.close();
          break;
        }
      }
    } finally {
      this.sending = false;
    }
  }

  private sendAsync(message: string | Uint8Array): Promise<void> {
    return new Promise((resolve, reject) => {
      this.socket.send(message, (err: any) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  public close() {
    try {
      this.socket.close();
    } catch {}
    this.onDisconnect(this.id);
  }
}

export class WebSocketManager {
  private connections = new Map<number, WebSocketConnection>();
  private nextId = 1;

  constructor(private metrics: MetricsRegistry) {}

  public connect(socket: WebSocket): number {
    const id = this.nextId++;
    const connection = new WebSocketConnection(id, socket, this.metrics, (connId) => {
      if (this.connections.delete(connId)) {
        this.metrics.ws_connections_active.dec();
      }
    });
    this.connections.set(id, connection);
    this.metrics.ws_connections_active.inc();
    return id;
  }

  public disconnect(id: number) {
    const connection = this.connections.get(id);
    if (connection) {
      connection.close();
    }
  }

  public broadcast(message: string | Uint8Array) {
    for (const connection of this.connections.values()) {
      connection.enqueue(message);
    }
  }

  public shutdown() {
    for (const connection of this.connections.values()) {
      connection.close();
    }
    this.connections.clear();
  }
}
