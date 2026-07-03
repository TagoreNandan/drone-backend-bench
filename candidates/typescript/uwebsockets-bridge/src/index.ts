import uWS from "uWebSockets.js";
import dgram from "dgram";
import { MavLinkPacketSplitter, MavLinkPacketParser, common, minimal } from "node-mavlink";
import { encode } from "@msgpack/msgpack";
import dotenv from "dotenv";
import { MetricsRegistry } from "./metrics.js";
import { WebSocketManager } from "./websocket_manager.js";

dotenv.config();

const port = parseInt(process.env.PORT || "8000", 10);
const host = process.env.HOST || "0.0.0.0";
const mavlinkPort = parseInt(process.env.MAVLINK_PORT || "14550", 10);

const metrics = new MetricsRegistry();
const websocketManager = new WebSocketManager(metrics);

// Create uWebSockets.js App
const app = uWS.App({});

// Helper to record HTTP requests
function handleHttpRequest(res: uWS.HttpResponse, req: uWS.HttpRequest, handler: () => { body: string | Buffer; contentType: string; status: number }) {
  const startNs = process.hrtime.bigint();
  const method = req.getMethod().toUpperCase();
  const path = req.getUrl();

  res.onAborted(() => {
    // request was aborted
  });

  const result = handler();

  res.writeStatus(result.status === 200 ? "200 OK" : "500 Internal Server Error");
  res.writeHeader("Content-Type", result.contentType);
  res.end(result.body);

  const durationNs = process.hrtime.bigint() - startNs;
  const durationMs = Number(durationNs) / 1_000_000;
  metrics.recordHttpRequest(path, method, result.status.toString(), durationMs);
}

// Health endpoints
app.get("/health", (res, req) => {
  handleHttpRequest(res, req, () => ({
    body: JSON.stringify({ status: "ok" }),
    contentType: "application/json",
    status: 200
  }));
});

app.get("/api/v1/health", (res, req) => {
  handleHttpRequest(res, req, () => ({
    body: JSON.stringify({ status: "ok" }),
    contentType: "application/json",
    status: 200
  }));
});

// Metrics endpoint
app.get("/metrics", (res, req) => {
  handleHttpRequest(res, req, () => ({
    body: metrics.render(),
    contentType: "text/plain; version=0.0.4; charset=utf-8",
    status: 200
  }));
});

// WebSocket Configuration
const wsConfig: uWS.WebSocketBehavior<any> = {
  compression: uWS.SHARED_COMPRESSOR,
  maxPayloadLength: 16 * 1024 * 1024,
  idleTimeout: 60,
  open: (ws) => {
    websocketManager.connect(ws);
  },
  message: (ws, message, isBinary) => {
    // We only send binary telemetry, no client messages expected
  },
  close: (ws, code, message) => {
    websocketManager.disconnect(ws);
  }
};

app.ws("/ws/telemetry", wsConfig);
app.ws("/api/v1/ws/telemetry", wsConfig);

// MAVLink listener
function startMAVLinkListener(port: number) {
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
        metrics.recordTelemetryDecode(elapsedMs);

        websocketManager.broadcast(msgpackData);
      }
    } catch (err) {
      // Ignore parsing errors
    }
  });

  socket.bind(port, "0.0.0.0", () => {
    console.log(`MAVLink UDP listener running on port ${port}`);
  });
}

// Start HTTP/WS Server
app.listen(port, (token) => {
  if (token) {
    console.log(`Server running on http://0.0.0.0:${port}`);
    startMAVLinkListener(mavlinkPort);
  } else {
    console.error(`Failed to start server on port ${port}`);
  }
});
