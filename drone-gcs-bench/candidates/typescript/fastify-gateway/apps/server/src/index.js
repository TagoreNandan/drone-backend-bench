import Fastify from "fastify";
import fastifyWebsocket from "@fastify/websocket";
import "@fastify-gateway/env/server";
import { InMemoryTelemetryStore } from "./store.js";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";
const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);
const metrics = new MetricsRegistry();
const store = new InMemoryTelemetryStore();
const websocketManager = new WebSocketManager(metrics);
const fastify = Fastify({
    logger: true,
    ajv: {
        customOptions: {
            removeAdditional: false,
            useDefaults: true,
            coerceTypes: true,
            allErrors: true,
        },
    },
});
// Register WebSocket plugin
await fastify.register(fastifyWebsocket);
// Validation Schemas
const registerSchema = {
    body: {
        type: "object",
        required: ["drone_id", "model"],
        additionalProperties: false,
        properties: {
            drone_id: { type: "string", minLength: 1 },
            model: { type: "string", minLength: 1 },
        },
    },
};
const telemetrySchema = {
    body: {
        type: "object",
        required: ["run_id", "drone_id", "seq", "timestamp", "payload"],
        additionalProperties: false,
        properties: {
            run_id: { type: "string", minLength: 1 },
            drone_id: { type: "string", minLength: 1 },
            seq: { type: "integer", minimum: 0 },
            timestamp: { type: "integer", minimum: 0 },
            payload: {
                type: "object",
                required: ["lat", "lon", "alt", "roll", "pitch", "yaw", "battery", "mode"],
                additionalProperties: false,
                properties: {
                    lat: { type: "number" },
                    lon: { type: "number" },
                    alt: { type: "number" },
                    roll: { type: "number" },
                    pitch: { type: "number" },
                    yaw: { type: "number" },
                    battery: { type: "integer", minimum: 0, maximum: 100 },
                    mode: { type: "string", minLength: 1 },
                },
            },
        },
    },
};
// Custom Error Handler for identical validation response structures
fastify.setErrorHandler((error, _request, reply) => {
    const err = error;
    if (err.validation) {
        const message = err.validation
            .map((e) => {
            const field = e.instancePath ? `${e.instancePath.substring(1)}` : "";
            return field ? `${field}: ${e.message}` : `${e.message}`;
        })
            .join(", ");
        return reply.status(400).send({
            error: {
                code: "INVALID_REQUEST",
                message: message || err.message,
            },
        });
    }
    return reply.status(500).send({
        error: {
            code: "INTERNAL_ERROR",
            message: "Internal error",
        },
    });
});
// Middleware hooks for HTTP Metrics Tracking
const startTimes = new WeakMap();
fastify.addHook("onRequest", async (request) => {
    startTimes.set(request, process.hrtime.bigint());
});
fastify.addHook("onResponse", async (request, reply) => {
    const startNs = startTimes.get(request);
    if (!startNs)
        return;
    const durationNs = process.hrtime.bigint() - startNs;
    const durationMs = Number(durationNs) / 1_000_000;
    const route = request.routeOptions?.url || request.url;
    metrics.recordHttpRequest(route, request.method, reply.statusCode.toString(), durationMs);
});
// Endpoints
fastify.post("/api/v1/drones/register", { schema: registerSchema }, async (request) => {
    const body = request.body;
    await store.registerDrone(body.drone_id, body.model);
    return { status: "ok", drone_id: body.drone_id };
});
fastify.post("/api/v1/telemetry", { schema: telemetrySchema }, async (request) => {
    const startNs = process.hrtime.bigint();
    const body = request.body;
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
    return { status: "ok" };
});
fastify.get("/api/v1/drones", async () => {
    const drones = await store.listActiveDrones();
    return { drones };
});
fastify.get("/api/v1/health", async () => {
    return { status: "ok" };
});
fastify.get("/metrics", async (_request, reply) => {
    reply.type("text/plain; version=0.0.4; charset=utf-8");
    return metrics.render();
});
// Handle WebSocket connections at both paths
const handleWsConnection = (connection) => {
    const socket = connection.socket;
    const connId = websocketManager.connect(socket);
    socket.on("message", () => {
        // Discard client incoming messages
    });
    socket.on("close", () => {
        websocketManager.disconnect(connId);
    });
    socket.on("error", () => {
        websocketManager.disconnect(connId);
    });
};
fastify.get("/ws/telemetry", { websocket: true }, handleWsConnection);
fastify.get("/api/v1/ws/telemetry", { websocket: true }, handleWsConnection);
// Start Server
const start = async () => {
    try {
        await fastify.listen({ host, port });
        console.log(`Server running on http://${host}:${port}`);
    }
    catch (err) {
        fastify.log.error(err);
        process.exit(1);
    }
};
start();
