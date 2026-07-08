export function droneId(droneIndex) {
  return `drone-${String(droneIndex).padStart(5, "0")}`;
}

export function registrationPayload(droneIndex) {
  return {
    drone_id: droneId(droneIndex),
    model: "benchmark-quadcopter",
  };
}

export function telemetryEnvelope({ runId, droneIndex, seq }) {
  const headingBase = (droneIndex * 13 + seq * 7) % 360;
  return {
    run_id: runId,
    drone_id: droneId(droneIndex),
    seq,
    timestamp: Date.now(),
    payload: {
      lat: 37.400001 + droneIndex * 0.00001 + seq * 0.000001,
      lon: -122.100001 + droneIndex * 0.00001 + seq * 0.000001,
      alt: 10 + (droneIndex % 10),
      roll: (headingBase % 10) * 0.1,
      pitch: ((headingBase + 3) % 10) * 0.1,
      yaw: headingBase,
      battery: Math.max(0, 100 - (seq % 100)),
      mode: "AUTO",
    },
  };
}
