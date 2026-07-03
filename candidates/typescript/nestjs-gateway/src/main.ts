import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { Module, Controller, Post, Get, Body, Res } from '@nestjs/common';
import { ExpressAdapter } from '@nestjs/platform-express';
import express from 'express';
import { WebSocketServer } from 'ws';
import dotenv from 'dotenv';
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

function validateZod(schema: z.ZodSchema, body: any) {
  const result = schema.safeParse(body);
  if (!result.success) {
    const message = result.error.errors
      .map((e) => {
        const path = e.path.join(".");
        return path ? `${path}: ${e.message}` : e.message;
      })
      .join(", ");
    throw new Error(message);
  }
  return result.data;
}

@Controller()
class AppController {
  @Post("/api/v1/drones/register")
  async register(@Body() body: any, @Res() res: any) {
    try {
      const data = validateZod(registerSchema, body);
      await store.registerDrone(data.drone_id, data.model);
      return res.status(200).json({ status: "ok", drone_id: data.drone_id });
    } catch (err: any) {
      return res.status(400).json({
        error: {
          code: "INVALID_REQUEST",
          message: err.message,
        }
      });
    }
  }

  @Post("/api/v1/telemetry")
  async telemetry(@Body() body: any, @Res() res: any) {
    const startNs = process.hrtime.bigint();
    try {
      const data = validateZod(telemetrySchema, body) as TelemetryEnvelope;
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

      return res.status(200).json({ status: "ok" });
    } catch (err: any) {
      return res.status(400).json({
        error: {
          code: "INVALID_REQUEST",
          message: err.message,
        }
      });
    }
  }

  @Get("/api/v1/drones")
  async listDrones(@Res() res: any) {
    const drones = await store.listActiveDrones();
    return res.status(200).json({ drones });
  }

  @Get("/api/v1/health")
  async health(@Res() res: any) {
    return res.status(200).json({ status: "ok" });
  }

  @Get("/metrics")
  async getMetrics(@Res() res: any) {
    res.set("Content-Type", "text/plain; version=0.0.4; charset=utf-8");
    return res.status(200).send(metrics.render());
  }
}

@Module({
  controllers: [AppController],
})
class AppModule {}

async function bootstrap() {
  const server = express();
  server.use(express.json());

  server.use((req, res, next) => {
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

  const app = await NestFactory.create(AppModule, new ExpressAdapter(server));
  await app.init();

  const httpServer = app.getHttpServer();

  const wsServer1 = new WebSocketServer({ noServer: true });
  const wsServer2 = new WebSocketServer({ noServer: true });

  const handleConnection = (socket: any) => {
    const connId = websocketManager.connect(socket);
    socket.on("message", () => {});
    socket.on("close", () => websocketManager.disconnect(connId));
    socket.on("error", () => websocketManager.disconnect(connId));
  };

  wsServer1.on("connection", handleConnection);
  wsServer2.on("connection", handleConnection);

  httpServer.on("upgrade", (request: any, socket: any, head: any) => {
    const pathname = new URL(request.url, `http://${request.headers.host}`).pathname;
    if (pathname === "/ws/telemetry") {
      wsServer1.handleUpgrade(request, socket, head, (ws) => {
        wsServer1.emit("connection", ws, request);
      });
    } else if (pathname === "/api/v1/ws/telemetry") {
      wsServer2.handleUpgrade(request, socket, head, (ws) => {
        wsServer2.emit("connection", ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  httpServer.listen(port, host, () => {
    console.log(`Server running on http://${host}:${port}`);
  });
}

bootstrap();
