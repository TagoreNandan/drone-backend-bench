export class InMemoryTelemetryStore {
    droneModels = new Map();
    latestTelemetryMap = new Map();
    async registerDrone(droneId, model) {
        this.droneModels.set(droneId, model);
    }
    async recordTelemetry(telemetry) {
        this.latestTelemetryMap.set(telemetry.drone_id, telemetry);
        if (!this.droneModels.has(telemetry.drone_id)) {
            this.droneModels.set(telemetry.drone_id, "");
        }
    }
    async listActiveDrones() {
        return Array.from(this.droneModels.keys()).sort();
    }
    async latestTelemetry(droneId) {
        return this.latestTelemetryMap.get(droneId) || null;
    }
}
