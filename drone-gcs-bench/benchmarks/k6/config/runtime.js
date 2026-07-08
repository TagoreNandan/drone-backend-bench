import { resolveProfile } from "./profiles.js";

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_PROFILE = "100";
const DEFAULT_SCENARIO = "health";

function parsePositiveInt(value, fallback) {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Expected a positive integer, got: ${value}`);
  }
  return parsed;
}

function normalizeBaseUrl(baseUrl) {
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

function deriveWebSocketUrl(baseUrl) {
  if (baseUrl.startsWith("https://")) {
    return `wss://${baseUrl.slice("https://".length)}`;
  }
  if (baseUrl.startsWith("http://")) {
    return `ws://${baseUrl.slice("http://".length)}`;
  }
  throw new Error(`BASE_URL must start with http:// or https://, got: ${baseUrl}`);
}

export function getRuntimeConfig() {
  const profileName = __ENV.PROFILE || DEFAULT_PROFILE;
  const profile = resolveProfile(profileName);
  const baseUrl = normalizeBaseUrl(__ENV.BASE_URL || DEFAULT_BASE_URL);

  const droneCount = parsePositiveInt(__ENV.DRONE_COUNT, profile.droneCount);
  const vus = parsePositiveInt(__ENV.VUS, profile.vus);
  const telemetryRate = parsePositiveInt(__ENV.TELEMETRY_RATE, profile.telemetryRate);
  const wsSessionSeconds = parsePositiveInt(__ENV.WS_SESSION_SECONDS, 10);

  return {
    scenarioName: __ENV.SCENARIO || DEFAULT_SCENARIO,
    profileName,
    baseUrl,
    wsBaseUrl: __ENV.WS_URL || deriveWebSocketUrl(baseUrl),
    duration: __ENV.DURATION || profile.duration,
    droneCount,
    vus,
    telemetryRate,
    wsSessionSeconds,
    runId: __ENV.RUN_ID || `k6-${profileName}`,
    registerDrones: (__ENV.REGISTER_DRONES || "true").toLowerCase() !== "false",
    apiPrefix: "/api/v1",
    wsTelemetryPath: "/ws/telemetry",
  };
}
