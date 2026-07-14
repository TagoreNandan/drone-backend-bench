import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { createNodeWebSocket } from "@hono/node-ws";
import dgram from "dgram";
import { MavLinkPacketSplitter, MavLinkPacketParser, common, minimal } from "node-mavlink";
import { encode } from "@msgpack/msgpack";
import "@hono-gateway/env/server";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";

const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);
const mavlinkPort = parseInt(process.env.MAVLINK_PORT || "14550", 10);

const metrics = new MetricsRegistry();
const websocketManager = new WebSocketManager(metrics);

type Variables = {};

const app = new Hono<{ Variables: Variables }>();

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
  metrics.recordHttpRequest(
    route,
    c.req.method,
    c.res.status.toString(),
    durationMs
  );
});

// Endpoints
app.get("/health", async (c) => {
  return c.json({ status: "ok" });
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
      const socket = ws.raw as any;
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
const server = serve(
  {
    fetch: app.fetch,
    port,
    hostname: host,
  },
  (info) => {
    console.log(`Server running on http://${info.address}:${info.port}`);
    startMAVLinkListener(mavlinkPort, websocketManager, metrics);
  }
);

injectWebSocket(server);
