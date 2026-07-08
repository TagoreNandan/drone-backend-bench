package models

import (
	"fmt"
)

type DroneRegistrationRequest struct {
	DroneID string `json:"drone_id"`
	Model   string `json:"model"`
}

func (req *DroneRegistrationRequest) Validate() error {
	if req.DroneID == "" {
		return fmt.Errorf("drone_id is required")
	}
	if req.Model == "" {
		return fmt.Errorf("model is required")
	}
	return nil
}

type TelemetryPayload struct {
	Lat     *float64 `json:"lat"`
	Lon     *float64 `json:"lon"`
	Alt     *float64 `json:"alt"`
	Roll    *float64 `json:"roll"`
	Pitch   *float64 `json:"pitch"`
	Yaw     *float64 `json:"yaw"`
	Battery *int     `json:"battery"`
	Mode    string   `json:"mode"`
}

func (payload *TelemetryPayload) Validate() error {
	if payload.Lat == nil {
		return fmt.Errorf("payload.lat is required")
	}
	if payload.Lon == nil {
		return fmt.Errorf("payload.lon is required")
	}
	if payload.Alt == nil {
		return fmt.Errorf("payload.alt is required")
	}
	if payload.Roll == nil {
		return fmt.Errorf("payload.roll is required")
	}
	if payload.Pitch == nil {
		return fmt.Errorf("payload.pitch is required")
	}
	if payload.Yaw == nil {
		return fmt.Errorf("payload.yaw is required")
	}
	if payload.Battery == nil {
		return fmt.Errorf("payload.battery is required")
	}
	if *payload.Battery < 0 || *payload.Battery > 100 {
		return fmt.Errorf("payload.battery must be between 0 and 100")
	}
	if payload.Mode == "" {
		return fmt.Errorf("payload.mode is required")
	}
	return nil
}

type TelemetryEnvelope struct {
	RunID     string            `json:"run_id"`
	DroneID   string            `json:"drone_id"`
	Seq       *int              `json:"seq"`
	Timestamp *int64            `json:"timestamp"`
	Payload   *TelemetryPayload `json:"payload"`
}

func (env *TelemetryEnvelope) Validate() error {
	if env.RunID == "" {
		return fmt.Errorf("run_id is required")
	}
	if env.DroneID == "" {
		return fmt.Errorf("drone_id is required")
	}
	if env.Seq == nil {
		return fmt.Errorf("seq is required")
	}
	if *env.Seq < 0 {
		return fmt.Errorf("seq must be >= 0")
	}
	if env.Timestamp == nil {
		return fmt.Errorf("timestamp is required")
	}
	if *env.Timestamp < 0 {
		return fmt.Errorf("timestamp must be >= 0")
	}
	if env.Payload == nil {
		return fmt.Errorf("payload is required")
	}
	return env.Payload.Validate()
}
