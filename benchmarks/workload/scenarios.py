"""Deterministic flight scenario generators for drone simulation."""

import math
from typing import Dict, Any, Tuple

# Zurich Reference Coordinates
ORIGIN_LAT = 47.3769
ORIGIN_LON = 8.5417
ORIGIN_ALT = 400.0  # AMSL in meters

M_TO_LAT = 1.0 / 111320.0
M_TO_LON = 1.0 / (111320.0 * math.cos(math.radians(ORIGIN_LAT)))


def _get_noise(seed: int, drone_idx: int, t: float, scale: float = 1.0) -> float:
    """Generate deterministic, pseudo-random float noise at time t using sine waves."""
    # Combine seed, drone index, and t to create a unique frequency phase
    val = (
        math.sin(seed * 0.13 + drone_idx * 7.42 + t * 5.79) * 0.43
        + math.sin(seed * 0.91 + drone_idx * 1.37 - t * 2.13) * 0.27
    )
    return val * scale


def get_start_position(drone_idx: int, num_drones: int) -> Tuple[float, float, float]:
    """Distribute drones in a deterministic grid spacing of 10 meters."""
    grid_size = int(math.ceil(math.sqrt(num_drones)))
    row = drone_idx // grid_size
    col = drone_idx % grid_size

    lat_offset = (row - (grid_size - 1) / 2.0) * 10.0
    lon_offset = (col - (grid_size - 1) / 2.0) * 10.0

    # Stagger starting altitudes between 10m and 30m above origin
    start_alt = ORIGIN_ALT + 10.0 + (drone_idx % 5) * 4.0

    lat = ORIGIN_LAT + lat_offset * M_TO_LAT
    lon = ORIGIN_LON + lon_offset * M_TO_LON
    return lat, lon, start_alt


def compute_hover(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Drone stays stationary, battery drains normally, stabil mode."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    battery = max(0, int(100 - (t / duration) * 20.0))  # 20% drain over run

    # Tiny fluctuations to simulate hovering noise
    lat = start_lat + _get_noise(seed, drone_idx, t, 0.05) * M_TO_LAT
    lon = start_lon + _get_noise(seed + 1, drone_idx, t, 0.05) * M_TO_LON
    alt = start_alt + _get_noise(seed + 2, drone_idx, t, 0.1)

    roll = _get_noise(seed + 3, drone_idx, t, 2.0)  # in deg
    pitch = _get_noise(seed + 4, drone_idx, t, 2.0)
    yaw = (drone_idx * 30.0 + _get_noise(seed + 5, drone_idx, t, 5.0)) % 360.0

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": math.radians(roll),
        "pitch": math.radians(pitch),
        "yaw": math.radians(yaw),
        "battery": battery,
        "mode": "HOVER",
    }
    return payload, 0.0, 0.0, 0.0


def compute_straight_flight(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Drones fly north in a straight line at 5 m/s."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    speed = 5.0  # m/s
    distance = speed * t

    lat = start_lat + distance * M_TO_LAT
    lon = start_lon
    alt = start_alt

    # Slight pitch forward due to forward acceleration
    pitch = 5.0 + _get_noise(seed + 1, drone_idx, t, 0.5)
    roll = _get_noise(seed + 2, drone_idx, t, 0.5)
    yaw = 0.0

    battery = max(0, int(100 - (t / duration) * 25.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": math.radians(roll),
        "pitch": math.radians(pitch),
        "yaw": math.radians(yaw),
        "battery": battery,
        "mode": "GUIDED",
    }
    return payload, 0.0, speed, 0.0


def compute_waypoint_mission(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Follows a rectangle pattern: 50m North -> 50m East -> 50m South -> 50m West."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    speed = 6.0  # m/s
    total_length = 200.0  # 50m * 4
    total_length / speed  # 33.3s

    pos_in_cycle = (t * speed) % total_length

    dx = 0.0
    dy = 0.0
    vx = 0.0
    vy = 0.0
    yaw_deg = 0.0

    if pos_in_cycle < 50.0:
        dy = pos_in_cycle  # flying North (Y)
        vy = speed
        yaw_deg = 0.0
    elif pos_in_cycle < 100.0:
        dy = 50.0
        dx = pos_in_cycle - 50.0  # flying East (X)
        vx = speed
        yaw_deg = 90.0
    elif pos_in_cycle < 150.0:
        dx = 50.0
        dy = 50.0 - (pos_in_cycle - 100.0)  # flying South (Y)
        vy = -speed
        yaw_deg = 180.0
    else:
        dx = 50.0 - (pos_in_cycle - 150.0)  # flying West (X)
        vx = -speed
        yaw_deg = 270.0

    lat = start_lat + dy * M_TO_LAT
    lon = start_lon + dx * M_TO_LON
    alt = start_alt

    # Roll into turns, pitch when moving
    pitch = 4.0 if (vy != 0.0) else 0.0
    roll = -4.0 if (vx != 0.0) else 0.0

    battery = max(0, int(100 - (t / duration) * 30.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": math.radians(roll),
        "pitch": math.radians(pitch),
        "yaw": math.radians(yaw_deg),
        "battery": battery,
        "mode": "AUTO",
    }
    return payload, vx, vy, 0.0


def compute_circular_orbit(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Drones orbit a point 20m away from their starting position."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    radius = 20.0  # meters
    omega = 0.2  # rad/s (~31s period)
    theta = omega * t + (drone_idx * (2 * math.pi / min(num_drones, 20)))

    # Circle center relative to start: center at start_x + radius
    dx = radius * math.cos(theta)
    dy = radius * math.sin(theta)

    # Velocity components
    vx = -radius * omega * math.sin(theta)
    vy = radius * omega * math.cos(theta)

    lat = start_lat + dy * M_TO_LAT
    lon = start_lon + dx * M_TO_LON
    alt = start_alt

    yaw = (math.degrees(theta) + 90.0) % 360.0
    roll = -5.0  # bank into circle
    pitch = 2.0

    battery = max(0, int(100 - (t / duration) * 28.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": math.radians(roll),
        "pitch": math.radians(pitch),
        "yaw": math.radians(yaw),
        "battery": battery,
        "mode": "GUIDED",
    }
    return payload, vx, vy, 0.0


def compute_figure_eight(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Lemniscate of Bernoulli trajectory."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    a = 30.0  # scale parameter
    omega = 0.12  # angular velocity
    theta = omega * t + (drone_idx * 0.4)

    denom = 1.0 + math.sin(theta) ** 2
    dx = (a * math.cos(theta)) / denom
    dy = (a * math.sin(theta) * math.cos(theta)) / denom

    # Calculate velocities via numerical diff
    dt = 0.01
    theta_next = theta + omega * dt
    denom_next = 1.0 + math.sin(theta_next) ** 2
    dx_next = (a * math.cos(theta_next)) / denom_next
    dy_next = (a * math.sin(theta_next) * math.cos(theta_next)) / denom_next

    vx = (dx_next - dx) / dt
    vy = (dy_next - dy) / dt

    lat = start_lat + dy * M_TO_LAT
    lon = start_lon + dx * M_TO_LON
    alt = start_alt

    yaw = math.degrees(math.atan2(vy, vx))
    roll = _get_noise(seed, drone_idx, t, 5.0)
    pitch = _get_noise(seed + 1, drone_idx, t, 5.0)

    battery = max(0, int(100 - (t / duration) * 32.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": math.radians(roll),
        "pitch": math.radians(pitch),
        "yaw": math.radians(yaw),
        "battery": battery,
        "mode": "GUIDED",
    }
    return payload, vx, vy, 0.0


def compute_battery_drain(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Battery discharges to 0% rapidly. When battery < 20%, it enters LAND mode."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    # Drain battery fully over the first 60% of duration
    drain_duration = duration * 0.6
    battery = max(0, int(100 - (t / drain_duration) * 100.0))

    mode = "HOVER"
    alt = start_alt
    vz = 0.0
    if battery < 20:
        mode = "LAND"
        # descend 1m/s
        descend_dist = (t - (drain_duration * 0.8)) * 1.0
        alt = max(ORIGIN_ALT, start_alt - max(0.0, descend_dist))
        vz = -1.0 if alt > ORIGIN_ALT else 0.0

    payload = {
        "lat": start_lat,
        "lon": start_lon,
        "alt": alt,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
        "battery": battery,
        "mode": mode,
    }
    return payload, 0.0, 0.0, vz


def compute_gps_drift(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Sinusoidal drift offset to GPS coordinates."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    # Slowly growing drift
    drift_scale = (t / duration) * 15.0  # up to 15 meters drift
    drift_x = drift_scale * math.sin(0.1 * t)
    drift_y = drift_scale * math.cos(0.08 * t)

    lat = start_lat + drift_y * M_TO_LAT
    lon = start_lon + drift_x * M_TO_LON

    battery = max(0, int(100 - (t / duration) * 20.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": start_alt,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
        "battery": battery,
        "mode": "LOITER",
    }
    return payload, 0.0, 0.0, 0.0


def compute_swarm(
    drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Whole swarm flock moves together along a waypoint track while maintaining grid offset."""
    start_lat, start_lon, start_alt = get_start_position(drone_idx, num_drones)

    # Leader trajectory (flying east at 4 m/s)
    speed = 4.0
    distance = speed * t

    lat = start_lat
    lon = start_lon + distance * M_TO_LON
    alt = start_alt

    battery = max(0, int(100 - (t / duration) * 25.0))

    payload = {
        "lat": lat,
        "lon": lon,
        "alt": alt,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": math.radians(90.0),
        "battery": battery,
        "mode": "AUTO",
    }
    return payload, speed, 0.0, 0.0


def generate_payload(
    scenario: str, drone_idx: int, num_drones: int, t: float, duration: float, seed: int
) -> Tuple[Dict[str, Any], float, float, float]:
    """Route to corresponding scenario mathematical generator."""
    name = scenario.lower().replace("-", "_")
    if name == "hover" or name == "telemetry_burst":
        return compute_hover(drone_idx, num_drones, t, duration, seed)
    elif name == "straight_flight":
        return compute_straight_flight(drone_idx, num_drones, t, duration, seed)
    elif name == "waypoint_mission":
        return compute_waypoint_mission(drone_idx, num_drones, t, duration, seed)
    elif name == "circular_orbit":
        return compute_circular_orbit(drone_idx, num_drones, t, duration, seed)
    elif name == "figure_eight":
        return compute_figure_eight(drone_idx, num_drones, t, duration, seed)
    elif name == "battery_drain":
        return compute_battery_drain(drone_idx, num_drones, t, duration, seed)
    elif name == "gps_drift":
        return compute_gps_drift(drone_idx, num_drones, t, duration, seed)
    elif name == "multi_drone_swarm":
        return compute_swarm(drone_idx, num_drones, t, duration, seed)
    else:
        # Fallback to hover
        return compute_hover(drone_idx, num_drones, t, duration, seed)
