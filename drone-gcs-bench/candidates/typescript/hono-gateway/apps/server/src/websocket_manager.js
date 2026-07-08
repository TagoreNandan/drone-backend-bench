import { WebSocket } from "ws";
import { MetricsRegistry } from "./metrics.js";
export class WebSocketConnection {
    id;
    socket;
    metrics;
    onDisconnect;
    queue = [];
    sending = false;
    constructor(id, socket, metrics, onDisconnect) {
        this.id = id;
        this.socket = socket;
        this.metrics = metrics;
        this.onDisconnect = onDisconnect;
    }
    enqueue(message) {
        if (this.queue.length >= 2048) {
            this.metrics.recordWsDrop();
            return;
        }
        this.queue.push(message);
        this.startSending();
    }
    async startSending() {
        if (this.sending)
            return;
        this.sending = true;
        try {
            while (this.queue.length > 0) {
                const message = this.queue.shift();
                const startNs = process.hrtime.bigint();
                try {
                    await this.sendAsync(message);
                    const elapsedNs = process.hrtime.bigint() - startNs;
                    const elapsedMs = Number(elapsedNs) / 1_000_000;
                    this.metrics.recordWsSend(elapsedMs);
                }
                catch (err) {
                    this.metrics.recordWsDrop();
                    this.close();
                    break;
                }
            }
        }
        finally {
            this.sending = false;
        }
    }
    sendAsync(message) {
        return new Promise((resolve, reject) => {
            this.socket.send(message, (err) => {
                if (err)
                    reject(err);
                else
                    resolve();
            });
        });
    }
    close() {
        try {
            this.socket.close();
        }
        catch { }
        this.onDisconnect(this.id);
    }
}
export class WebSocketManager {
    metrics;
    connections = new Map();
    nextId = 1;
    constructor(metrics) {
        this.metrics = metrics;
    }
    connect(socket) {
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
    disconnect(id) {
        const connection = this.connections.get(id);
        if (connection) {
            connection.close();
        }
    }
    broadcast(message) {
        for (const connection of this.connections.values()) {
            connection.enqueue(message);
        }
    }
    shutdown() {
        for (const connection of this.connections.values()) {
            connection.close();
        }
        this.connections.clear();
    }
}
