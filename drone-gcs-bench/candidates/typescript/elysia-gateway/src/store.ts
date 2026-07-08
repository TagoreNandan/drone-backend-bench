export interface TelemetryPayload {
  lat: number;
  lon: number;
  alt: number;
  roll: number;
  pitch: number;
  yaw: number;
  battery: number;
  mode: string;
}

export interface TelemetryEnvelope {
  run_id: string;
  drone_id: string;
  seq: number;
  timestamp: number;
  payload: TelemetryPayload;
}

export class InMemoryTelemetryStore {
  private droneModels = new Map<string, string>();
  private latestTelemetryMap = new Map<string, TelemetryEnvelope>();

  public async registerDrone(droneId: string, model: string): Promise<void> {
    this.droneModels.set(droneId, model);
  }

  public async recordTelemetry(telemetry: TelemetryEnvelope): Promise<void> {
    this.latestTelemetryMap.set(telemetry.drone_id, telemetry);
    if (!this.droneModels.has(telemetry.drone_id)) {
      this.droneModels.set(telemetry.drone_id, "");
    }
  }

  public async listActiveDrones(): Promise<string[]> {
    return Array.from(this.droneModels.keys()).sort();
  }

  public async latestTelemetry(droneId: string): Promise<TelemetryEnvelope | null> {
    return this.latestTelemetryMap.get(droneId) || null;
  }
}
