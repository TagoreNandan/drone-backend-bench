import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { createNodeWebSocket } from "@hono/node-ws";
import { z } from "zod";
import "@hono-gateway/env/server";
import { InMemoryTelemetryStore } from "./store.js";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";
const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);
const metrics = new MetricsRegistry();
const store = new InMemoryTelemetryStore();
const websocketManager = new WebSocketManager(metrics);
const app = new Hono();
// Zod validation schemas
const registerSchema = z.object({
    drone_id: z.string().min(1),
    model: z.string().min(1),
}).strict();
const telemetryPayloadSchema = z.object({
    lat: z.number(),
    lon: z.number(),
    alt: z.number(),
    roll: z.number(),
    pitch: z.number(),
    yaw: z.number(),
    battery: z.number().int().min(0).max(100),
    mode: z.string().min(1),
}).strict();
const telemetrySchema = z.object({
    run_id: z.string().min(1),
    drone_id: z.string().min(1),
    seq: z.number().int().min(0),
    timestamp: z.number().int().min(0),
    payload: telemetryPayloadSchema,
}).strict();
// Custom Validation Middleware for 400 response matching
const validateJson = (schema) => {
    return async (c, next) => {
        let body;
        try {
            body = await c.req.json();
        }
        catch (err) {
            return c.json({
                error: {
                    code: "INVALID_REQUEST",
                    message: err.message || "Invalid JSON",
                },
            }, 400);
        }
        const result = schema.safeParse(body);
        if (!result.success) {
            const message = result.error.issues
                .map((issue) => {
                const field = issue.path.join(".");
                return field ? `${field}: ${issue.message}` : `${issue.message}`;
            })
                .join(", ");
            return c.json({
                error: {
                    code: "INVALID_REQUEST",
                    message,
                },
            }, 400);
        }
        c.set("validBody", result.data);
        await next();
    };
};
// Global Error Handler
app.onError((_error, c) => {
    return c.json({
        error: {
            code: "INTERNAL_ERROR",
            message: "Internal error",
        },
    }, 500);
});
// HTTP Metrics Middleware
app.use("*", async (c, next) => {
    const startNs = process.hrtime.bigint();
    await next();
    const durationNs = process.hrtime.bigint() - startNs;
    const durationMs = Number(durationNs) / 1_000_000;
    const route = c.req.routePath || c.req.path;
    metrics.recordHttpRequest(route, c.req.method, c.res.status.toString(), durationMs);
});
// Endpoints
app.post("/api/v1/drones/register", validateJson(registerSchema), async (c) => {
    const body = c.get("validBody");
    await store.registerDrone(body.drone_id, body.model);
    return c.json({ status: "ok", drone_id: body.drone_id });
});
app.post("/api/v1/telemetry", validateJson(telemetrySchema), async (c) => {
    const startNs = process.hrtime.bigint();
    const body = c.get("validBody");
    await store.recordTelemetry(body);
    const message = {
        drone_id: body.drone_id,
        seq: body.seq,
        timestamp: body.timestamp,
        payload: body.payload,
    };
    websocketManager.broadcast(JSON.stringify(message));
    const elapsedNs = process.hrtime.bigint() - startNs;
    const elapsedMs = Number(elapsedNs) / 1_000_000;
    metrics.recordTelemetryIngest(elapsedMs);
    return c.json({ status: "ok" });
});
app.get("/api/v1/drones", async (c) => {
    const drones = await store.listActiveDrones();
    return c.json({ drones });
});
app.get("/api/v1/health", async (c) => {
    return c.json({ status: "ok" });
});
app.get("/metrics", async (c) => {
    c.header("Content-Type", "text/plain; version=0.0.4; charset=utf-8");
    return c.body(metrics.render());
});
// WebSocket support
const { injectWebSocket, upgradeWebSocket } = createNodeWebSocket({ app });
const handleWs = upgradeWebSocket((_c) => {
    return {
        onOpen(_event, ws) {
            const socket = ws.raw;
            const connId = websocketManager.connect(socket);
            socket.on("close", () => {
                websocketManager.disconnect(connId);
            });
            socket.on("error", () => {
                websocketManager.disconnect(connId);
            });
        },
    };
});
app.get("/ws/telemetry", handleWs);
app.get("/api/v1/ws/telemetry", handleWs);
// Start Server
const server = serve({
    fetch: app.fetch,
    port,
    hostname: host,
}, (info) => {
    console.log(`Server running on http://${info.address}:${info.port}`);
});
injectWebSocket(server);
