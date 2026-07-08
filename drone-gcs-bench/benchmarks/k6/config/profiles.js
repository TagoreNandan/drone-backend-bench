const profiles = {
  "100": {
    droneCount: 100,
    vus: 20,
    duration: "2m",
    telemetryRate: 2,
  },
  "500": {
    droneCount: 500,
    vus: 60,
    duration: "3m",
    telemetryRate: 2,
  },
  "1000": {
    droneCount: 1000,
    vus: 120,
    duration: "4m",
    telemetryRate: 2,
  },
  "5000": {
    droneCount: 5000,
    vus: 300,
    duration: "5m",
    telemetryRate: 1,
  },
};

export const LOAD_PROFILES = Object.freeze(profiles);

export function resolveProfile(profileName) {
  const resolved = LOAD_PROFILES[profileName];
  if (!resolved) {
    throw new Error(
      `Unknown PROFILE="${profileName}". Allowed values: ${Object.keys(LOAD_PROFILES).join(", ")}`
    );
  }
  return resolved;
}
