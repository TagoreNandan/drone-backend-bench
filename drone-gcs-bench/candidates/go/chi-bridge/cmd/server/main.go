package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"strconv"
	"time"

	"chi-bridge/internal/metrics"
	"chi-bridge/internal/ws"

	"github.com/bluenviron/gomavlib/v3"
	"github.com/bluenviron/gomavlib/v3/pkg/dialects/common"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/gorilla/websocket"
	"github.com/joho/godotenv"
	"github.com/vmihailenco/msgpack/v5"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

type statusResponseWriter struct {
	http.ResponseWriter
	status int
}

func (rw *statusResponseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *statusResponseWriter) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	hijacker, ok := rw.ResponseWriter.(http.Hijacker)
	if !ok {
		return nil, nil, fmt.Errorf("underlying response writer does not implement http.Hijacker")
	}
	return hijacker.Hijack()
}

func MetricsMiddleware(reg *metrics.MetricsRegistry) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			rw := &statusResponseWriter{ResponseWriter: w, status: http.StatusOK}
			next.ServeHTTP(rw, r)
			duration := time.Since(start).Seconds() * 1000.0 // in ms

			routePattern := ""
			rctx := chi.RouteContext(r.Context())
			if rctx != nil {
				routePattern = rctx.RoutePattern()
			}
			if routePattern == "" {
				routePattern = r.URL.Path
			}
			reg.RecordHttpRequest(routePattern, r.Method, strconv.Itoa(rw.status), duration)
		})
	}
}

func startMAVLinkListener(port int, wsManager *ws.WebSocketManager, reg *metrics.MetricsRegistry) {
	node := &gomavlib.Node{
		Endpoints: []gomavlib.EndpointConf{
			gomavlib.EndpointUDPServer{Address: fmt.Sprintf("0.0.0.0:%d", port)},
		},
		Dialect:     common.Dialect,
		OutVersion:  gomavlib.V2,
		OutSystemID: 10,
	}
	err := node.Initialize()
	if err != nil {
		fmt.Printf("Error starting MAVLink UDP listener: %v\n", err)
		return
	}
	defer node.Close()

	fmt.Printf("Starting MAVLink UDP listener on port %d...\n", port)

	for evt := range node.Events() {
		if frm, ok := evt.(*gomavlib.EventFrame); ok {
			msg := frm.Message()
			var msgType string
			data := map[string]interface{}{
				"sysid":  frm.SystemID(),
				"compid": frm.ComponentID(),
			}
			matched := false

			switch m := msg.(type) {
			case *common.MessageHeartbeat:
				msgType = "HEARTBEAT"
				data["type"] = uint8(m.Type)
				data["autopilot"] = uint8(m.Autopilot)
				data["system_status"] = uint8(m.SystemStatus)
				matched = true
			case *common.MessageAttitude:
				msgType = "ATTITUDE"
				data["time_boot_ms"] = m.TimeBootMs
				data["roll"] = m.Roll
				data["pitch"] = m.Pitch
				data["yaw"] = m.Yaw
				matched = true
			case *common.MessageGlobalPositionInt:
				msgType = "GLOBAL_POSITION_INT"
				data["lat"] = m.Lat
				data["lon"] = m.Lon
				data["alt"] = m.Alt
				data["relative_alt"] = m.RelativeAlt
				matched = true
			case *common.MessageSysStatus:
				msgType = "SYS_STATUS"
				data["battery_remaining"] = int8(m.BatteryRemaining)
				data["voltage_battery"] = m.VoltageBattery
				data["current_battery"] = m.CurrentBattery
				matched = true
			}

			if matched {
				start := time.Now()
				data["message_type"] = msgType
				
				payload, err := msgpack.Marshal(data)
				if err != nil {
					continue
				}

				elapsed := time.Since(start).Seconds() * 1000.0
				reg.RecordTelemetryDecode(elapsed)

				wsManager.Broadcast(payload)
			}
		}
	}
}

func main() {
	godotenv.Load()

	host := os.Getenv("HOST")
	if host == "" {
		host = "0.0.0.0"
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}
	addr := host + ":" + port

	metricsRegistry := metrics.NewRegistry()
	wsManager := ws.NewWebSocketManager(metricsRegistry)

	// Spawn UDP MAVLink Listener
	mavlinkPortStr := os.Getenv("MAVLINK_PORT")
	if mavlinkPortStr == "" {
		mavlinkPortStr = "14550"
	}
	mavlinkPort, err := strconv.Atoi(mavlinkPortStr)
	if err != nil {
		mavlinkPort = 14550
	}
	go startMAVLinkListener(mavlinkPort, wsManager, metricsRegistry)

	r := chi.NewRouter()

	r.Use(middleware.Recoverer)
	r.Use(MetricsMiddleware(metricsRegistry))

	// Routes
	healthHandler := func(w http.ResponseWriter, req *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "ok",
		})
	}
	r.Get("/health", healthHandler)
	r.Get("/api/v1/health", healthHandler)

	r.Get("/metrics", func(w http.ResponseWriter, req *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(metricsRegistry.Render()))
	})

	handleWS := func(w http.ResponseWriter, req *http.Request) {
		conn, err := upgrader.Upgrade(w, req, nil)
		if err != nil {
			return
		}
		connId := wsManager.Connect(conn)

		defer wsManager.Remove(connId)
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				break
			}
		}
	}

	r.Get("/ws/telemetry", handleWS)
	r.Get("/api/v1/ws/telemetry", handleWS)

	fmt.Printf("Server running on http://%s\n", addr)
	if err := http.ListenAndServe(addr, r); err != nil {
		panic("Failed to start server: " + err.Error())
	}
}
