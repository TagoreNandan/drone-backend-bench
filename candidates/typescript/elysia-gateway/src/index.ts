import { Elysia } from "elysia";
import dotenv from "dotenv";
import { z } from "zod";
import { InMemoryTelemetryStore, type TelemetryEnvelope } from "./store.js";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";

dotenv.config();

const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);

const metrics = new MetricsRegistry();
const store = new InMemoryTelemetryStore();
const websocketManager = new WebSocketManager(metrics);

// Zod Validation Schemas
const registerSchema = z.object({
  drone_id: z.string().min(1),
  model: z.string().min(1),
}).strict();

const telemetrySchema = z.object({
  run_id: z.string().min(1),
  drone_id: z.string().min(1),
  seq: z.number().int().nonnegative(),
  timestamp: z.number().int().nonnegative(),
  payload: z.object({
    lat: z.number(),
    lon: z.number(),
    alt: z.number(),
    roll: z.number(),
    pitch: z.number(),
    yaw: z.number(),
    battery: z.number().int().min(0).max(100),
    mode: z.string().min(1),
  }).strict(),
}).strict();

const startTimes = new WeakMap<any, bigint>();

const app = new Elysia()
  .onRequest(({ request }) => {
    startTimes.set(request, process.hrtime.bigint());
  })
  .onAfterResponse(({ request, set }) => {
    const startNs = startTimes.get(request);
    if (!startNs) return;
    const durationNs = process.hrtime.bigint() - startNs;
    const durationMs = Number(durationNs) / 1_000_000;

    const url = new URL(request.url);
    const route = url.pathname;
    const status = (set.status || 200).toString();

    metrics.recordHttpRequest(route, request.method, status, durationMs);
  })
  .onError(({ error, set }) => {
    set.status = 400;
    return {
      error: {
        code: "INVALID_REQUEST",
        message: error.message,
      }
    };
  })
  .post("/api/v1/drones/register", async ({ body, set }) => {
    const result = registerSchema.safeParse(body);
    if (!result.success) {
      const message = result.error.errors
        .map((e) => {
          const path = e.path.join(".");
          return path ? `${path}: ${e.message}` : e.message;
        })
        .join(", ");
      set.status = 400;
      return {
        error: {
          code: "INVALID_REQUEST",
          message,
        }
      };
    }

    const data = result.data;
    await store.registerDrone(data.drone_id, data.model);
    return { status: "ok", drone_id: data.drone_id };
  })
  .post("/api/v1/telemetry", async ({ body, set }) => {
    const startNs = process.hrtime.bigint();
    const result = telemetrySchema.safeParse(body);
    if (!result.success) {
      const message = result.error.errors
        .map((e) => {
          const path = e.path.join(".");
          return path ? `${path}: ${e.message}` : e.message;
        })
        .join(", ");
      set.status = 400;
      return {
        error: {
          code: "INVALID_REQUEST",
          message,
        }
      };
    }

    const data = result.data as TelemetryEnvelope;
    await store.recordTelemetry(data);

    const messageObj = {
      drone_id: data.drone_id,
      seq: data.seq,
      timestamp: data.timestamp,
      payload: data.payload,
    };
    websocketManager.broadcast(JSON.stringify(messageObj));

    const elapsedNs = process.hrtime.bigint() - startNs;
    const elapsedMs = Number(elapsedNs) / 1_000_000;
    metrics.recordTelemetryIngest(elapsedMs);

    return { status: "ok" };
  })
  .get("/api/v1/drones", async () => {
    const drones = await store.listActiveDrones();
    return { drones };
  })
  .get("/api/v1/health", async () => {
    return { status: "ok" };
  })
  .get("/metrics", async ({ set }) => {
    set.headers["content-type"] = "text/plain; version=0.0.4; charset=utf-8";
    return metrics.render();
  });

// WebSocket Configuration
const wsConfig = {
  open(ws: any) {
    const connId = websocketManager.connect(ws);
    ws.data = { connId };
  },
  message(ws: any, message: any) {
    // discard client messages
  },
  close(ws: any) {
    if (ws.data?.connId) {
      websocketManager.disconnect(ws.data.connId);
    }
  },
  error(ws: any) {
    if (ws.data?.connId) {
      websocketManager.disconnect(ws.data.connId);
    }
  }
};

app.ws("/ws/telemetry", wsConfig);
app.ws("/api/v1/ws/telemetry", wsConfig);

app.listen({ hostname: host, port }, () => {
  console.log(`Server running on http://${host}:${port}`);
});
