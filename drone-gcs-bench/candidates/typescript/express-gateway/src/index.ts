import express from "express";
import expressWs from "express-ws";
import dotenv from "dotenv";
import dgram from "dgram";
import { MavLinkPacketSplitter, MavLinkPacketParser, common, minimal } from "node-mavlink";
import { encode } from "@msgpack/msgpack";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";

dotenv.config();

const host = process.env.HOST || "0.0.0.0";
const port = parseInt(process.env.PORT || "8000", 10);
const mavlinkPort = parseInt(process.env.MAVLINK_PORT || "14550", 10);

const metrics = new MetricsRegistry();
const websocketManager = new WebSocketManager(metrics);

const baseApp = express();
const wsInstance = expressWs(baseApp);
const app = wsInstance.app;

app.use(express.json());

// Metrics Middleware
app.use((req, res, next) => {
  const startNs = process.hrtime.bigint();
  res.on("finish", () => {
    const durationNs = process.hrtime.bigint() - startNs;
    const durationMs = Number(durationNs) / 1_000_000;
    const route = req.route ? req.route.path : req.path;
    metrics.recordHttpRequest(
      route,
      req.method,
      res.statusCode.toString(),
      durationMs
    );
  });
  next();
});

// Endpoints
app.get("/health", (_req, res) => {
  res.status(200).json({ status: "ok" });
});

app.get("/api/v1/health", (_req, res) => {
  res.status(200).json({ status: "ok" });
});

app.get("/metrics", (_req, res) => {
  res.set("Content-Type", "text/plain; version=0.0.4; charset=utf-8");
  res.status(200).send(metrics.render());
});

// WebSocket connection handler
const handleWsConnection = (ws: any) => {
  const connId = websocketManager.connect(ws);

  ws.on("message", () => {
    // discard client messages
  });

  ws.on("close", () => {
    websocketManager.disconnect(connId);
  });

  ws.on("error", () => {
    websocketManager.disconnect(connId);
  });
};

app.ws("/ws/telemetry", handleWsConnection);
app.ws("/api/v1/ws/telemetry", handleWsConnection);

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

app.listen(port, host, () => {
  console.log(`Server running on http://${host}:${port}`);
  startMAVLinkListener(mavlinkPort, websocketManager, metrics);
});
