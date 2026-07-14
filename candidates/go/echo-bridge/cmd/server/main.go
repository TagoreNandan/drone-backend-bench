package main

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"

	"echo-bridge/internal/metrics"
	"echo-bridge/internal/ws"

	"github.com/bluenviron/gomavlib/v3"
	"github.com/bluenviron/gomavlib/v3/pkg/dialects/common"
	"github.com/gorilla/websocket"
	"github.com/joho/godotenv"
	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	"github.com/vmihailenco/msgpack/v5"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

func MetricsMiddleware(reg *metrics.MetricsRegistry) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			start := time.Now()
			err := next(c)
			duration := time.Since(start).Seconds() * 1000.0 // in ms

			status := strconv.Itoa(c.Response().Status)
			route := c.Path()
			if route == "" {
				route = c.Request().URL.Path
			}
			reg.RecordHttpRequest(route, c.Request().Method, status, duration)
			return err
		}
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

	e := echo.New()
	e.HideBanner = true
	e.HidePort = true

	e.Use(middleware.Recover())
	e.Use(MetricsMiddleware(metricsRegistry))

	// Routes
	healthHandler := func(c echo.Context) error {
		return c.JSON(http.StatusOK, map[string]interface{}{
			"status": "ok",
		})
	}
	e.GET("/health", healthHandler)
	e.GET("/api/v1/health", healthHandler)

	e.GET("/metrics", func(c echo.Context) error {
		return c.Blob(http.StatusOK, "text/plain; version=0.0.4; charset=utf-8", []byte(metricsRegistry.Render()))
	})

	handleWS := func(c echo.Context) error {
		conn, err := upgrader.Upgrade(c.Response().Writer, c.Request(), nil)
		if err != nil {
			return err
		}
		connId := wsManager.Connect(conn)

		defer wsManager.Remove(connId)
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				break
			}
		}
		return nil
	}

	e.GET("/ws/telemetry", handleWS)
	e.GET("/api/v1/ws/telemetry", handleWS)

	fmt.Printf("Server running on http://%s\n", addr)
	if err := e.Start(addr); err != nil {
		panic("Failed to start server: " + err.Error())
	}
}
