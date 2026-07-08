import Fastify from "fastify";
import fastifyWebsocket from "@fastify/websocket";
import "@fastify-gateway/env/server";
import dgram from "dgram";
import { MavLinkPacketSplitter, MavLinkPacketParser, common, minimal } from "node-mavlink";
import { encode } from "@msgpack/msgpack";
import { InMemoryTelemetryStore, type TelemetryEnvelope } from "./store.js";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";

const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);
const mavlinkPort = parseInt(process.env.MAVLINK_PORT || "14550", 10);

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
  const err = error as any;
  if (err.validation) {
    const message = err.validation
      .map((e: any) => {
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
const startTimes = new WeakMap<any, bigint>();

fastify.addHook("onRequest", async (request) => {
  startTimes.set(request, process.hrtime.bigint());
});

fastify.addHook("onResponse", async (request, reply) => {
  const startNs = startTimes.get(request);
  if (!startNs) return;
  const durationNs = process.hrtime.bigint() - startNs;
  const durationMs = Number(durationNs) / 1_000_000;

  const route = request.routeOptions?.url || request.url;
  metrics.recordHttpRequest(
    route,
    request.method,
    reply.statusCode.toString(),
    durationMs
  );
});

// Endpoints
fastify.post("/api/v1/drones/register", { schema: registerSchema }, async (request) => {
  const body = request.body as { drone_id: string; model: string };
  await store.registerDrone(body.drone_id, body.model);
  return { status: "ok", drone_id: body.drone_id };
});

fastify.post("/api/v1/telemetry", { schema: telemetrySchema }, async (request) => {
  const startNs = process.hrtime.bigint();
  const body = request.body as TelemetryEnvelope;
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

fastify.get("/health", async () => {
  return { status: "ok" };
});

fastify.get("/api/v1/health", async () => {
  return { status: "ok" };
});

fastify.get("/metrics", async (_request, reply) => {
  reply.type("text/plain; version=0.0.4; charset=utf-8");
  return metrics.render();
});

// Handle WebSocket connections at both paths
const handleWsConnection = (connection: any) => {
  const socket = connection.socket || connection;
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

// MAVLink listener
function startMAVLinkListener(port: number, wsManager: WebSocketManager, reg: MetricsRegistry) {
  const splitter = new MavLinkPacketSplitter();
  const parser = new MavLinkPacketParser();

  const REGISTRY: Record<number, any> = {
    ...minimal.REGISTRY,
    ...common.REGISTRY,
  };

  const socket = dgram.createSocket({ type: "udp4", reuseAddr: true });

  socket.on("message", (msg) => {
    splitter.write(msg);
  });

  splitter.pipe(parser);

  parser.on("data", (packet) => {
    const clazz = REGISTRY[packet.header.msgid];
    if (!clazz) return;

    try {
      const startNs = process.hrtime.bigint();
      const data = packet.protocol.data(packet.payload, clazz);

      let msgType: string | null = null;
      const payload: Record<string, any> = {
        sysid: packet.header.sysid,
        compid: packet.header.compid,
      };

      const msgid = packet.header.msgid;
      if (msgid === 0) { // HEARTBEAT
        msgType = "HEARTBEAT";
        payload.type = data.type;
        payload.autopilot = data.autopilot;
        payload.system_status = data.system_status;
      } else if (msgid === 30) { // ATTITUDE
        msgType = "ATTITUDE";
        payload.time_boot_ms = data.time_boot_ms;
        payload.roll = data.roll;
        payload.pitch = data.pitch;
        payload.yaw = data.yaw;
      } else if (msgid === 33) { // GLOBAL_POSITION_INT
        msgType = "GLOBAL_POSITION_INT";
        payload.lat = data.lat;
        payload.lon = data.lon;
        payload.alt = data.alt;
        payload.relative_alt = data.relative_alt;
      } else if (msgid === 1) { // SYS_STATUS
        msgType = "SYS_STATUS";
        payload.battery_remaining = data.battery_remaining;
        payload.voltage_battery = data.voltage_battery;
        payload.current_battery = data.current_battery;
      }

      if (msgType) {
        payload.message_type = msgType;
        const msgpackData = encode(payload);

        const elapsedNs = process.hrtime.bigint() - startNs;
        const elapsedMs = Number(elapsedNs) / 1_000_000;
        reg.recordTelemetryDecode(elapsedMs);

        wsManager.broadcast(msgpackData);
      }
    } catch (err) {
      // Ignore parsing errors
    }
  });

  socket.bind(port, "0.0.0.0", () => {
    console.log(`MAVLink UDP listener running on port ${port}`);
  });
}

// Start Server
const start = async () => {
  try {
    await fastify.listen({ host, port });
    console.log(`Server running on http://${host}:${port}`);
    startMAVLinkListener(mavlinkPort, websocketManager, metrics);
  } catch (err) {
    fastify.log.error(err as any);
    process.exit(1);
  }
};

start();
