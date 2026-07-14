package ws

import (
	"sync"
	"time"

	"echo-bridge/internal/metrics"

	"github.com/gorilla/websocket"
)

type WebSocketConnection struct {
	id        int
	conn      *websocket.Conn
	sendChan  chan []byte
	closeChan chan struct{}
	once      sync.Once
	metrics   *metrics.MetricsRegistry
	manager   *WebSocketManager
}

func NewConnection(id int, conn *websocket.Conn, metricsRegistry *metrics.MetricsRegistry, manager *WebSocketManager) *WebSocketConnection {
	c := &WebSocketConnection{
		id:        id,
		conn:      conn,
		sendChan:  make(chan []byte, 2048),
		closeChan: make(chan struct{}),
		metrics:   metricsRegistry,
		manager:   manager,
	}
	go c.writeLoop()
	return c
}

func (c *WebSocketConnection) Enqueue(msg []byte) {
	select {
	case c.sendChan <- msg:
	default:
		c.metrics.RecordWsDrop()
	}
}

func (c *WebSocketConnection) writeLoop() {
	defer c.Close()
	for {
		select {
		case msg, ok := <-c.sendChan:
			if !ok {
				return
			}
			start := time.Now()
			err := c.conn.WriteMessage(websocket.BinaryMessage, msg)
			if err != nil {
				c.metrics.RecordWsDrop()
				return
			}
			elapsed := time.Since(start).Seconds() * 1000.0
			c.metrics.RecordWsSend(elapsed)
		case <-c.closeChan:
			return
		}
	}
}

func (c *WebSocketConnection) Close() {
	c.once.Do(func() {
		close(c.closeChan)
		c.conn.Close()
		c.manager.Remove(c.id)
	})
}

type WebSocketManager struct {
	mu          sync.Mutex
	connections map[int]*WebSocketConnection
	nextId      int
	metrics     *metrics.MetricsRegistry
}

func NewWebSocketManager(metricsRegistry *metrics.MetricsRegistry) *WebSocketManager {
	return &WebSocketManager{
		connections: make(map[int]*WebSocketConnection),
		nextId:      1,
		metrics:     metricsRegistry,
	}
}

func (m *WebSocketManager) Connect(conn *websocket.Conn) int {
	m.mu.Lock()
	defer m.mu.Unlock()
	id := m.nextId
	m.nextId++

	connection := NewConnection(id, conn, m.metrics, m)
	m.connections[id] = connection
	m.metrics.WsConnectionsActive.Inc(1.0)
	return id
}

func (m *WebSocketManager) Remove(id int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.connections[id]; ok {
		delete(m.connections, id)
		m.metrics.WsConnectionsActive.Dec(1.0)
	}
}

func (m *WebSocketManager) Broadcast(msg []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, conn := range m.connections {
		conn.Enqueue(msg)
	}
}

func (m *WebSocketManager) Shutdown() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, conn := range m.connections {
		conn.Close()
	}
	m.connections = make(map[int]*WebSocketConnection)
}
