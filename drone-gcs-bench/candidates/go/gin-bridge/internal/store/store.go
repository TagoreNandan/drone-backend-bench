package store

import (
	"sort"
	"sync"

	"gin-bridge/internal/models"
)

type InMemoryTelemetryStore struct {
	mu             sync.RWMutex
	droneModels    map[string]string
	latestTelemetry map[string]models.TelemetryEnvelope
}

func NewStore() *InMemoryTelemetryStore {
	return &InMemoryTelemetryStore{
		droneModels:     make(map[string]string),
		latestTelemetry: make(map[string]models.TelemetryEnvelope),
	}
}

func (s *InMemoryTelemetryStore) RegisterDrone(droneID, model string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.droneModels[droneID] = model
	return nil
}

func (s *InMemoryTelemetryStore) RecordTelemetry(telemetry models.TelemetryEnvelope) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.latestTelemetry[telemetry.DroneID] = telemetry
	if _, ok := s.droneModels[telemetry.DroneID]; !ok {
		s.droneModels[telemetry.DroneID] = ""
	}
	return nil
}

func (s *InMemoryTelemetryStore) ListActiveDrones() ([]string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	drones := make([]string, 0, len(s.droneModels))
	for k := range s.droneModels {
		drones = append(drones, k)
	}
	sort.Strings(drones)
	return drones, nil
}

func (s *InMemoryTelemetryStore) LatestTelemetry(droneID string) (models.TelemetryEnvelope, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	telemetry, ok := s.latestTelemetry[droneID]
	return telemetry, ok
}
