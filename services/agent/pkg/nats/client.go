package nats

import (
	"container/ring"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/awatch/agent/pkg/config"
	"github.com/awatch/agent/pkg/models"
	"github.com/nats-io/nats.go"
)

type NATSClient struct {
	conn       *nats.Conn
	js         nats.JetStreamContext
	subject    string
	buffer     *ring.Ring
	bufferSize int
	mu         sync.Mutex
	config     *config.Config
}

type Payload struct {
	AgentID   string          `json:"agent_id"`
	Metrics   []models.Metric `json:"metrics"`
	Timestamp int64           `json:"timestamp"`
}

func NewNATSClient(cfg *config.Config) (*NATSClient, error) {
	nc := &NATSClient{
		subject:    cfg.NATSSubject,
		bufferSize: cfg.BufferSize,
		config:     cfg,
		buffer:     ring.New(cfg.BufferSize),
	}

	opts := []nats.Option{
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2 * time.Second),
		nats.DisconnectErrHandler(func(nc *nats.Conn, err error) {
			if err != nil {
				log.Printf("NATS disconnected: %v", err)
			}
		}),
		nats.ReconnectHandler(func(nc *nats.Conn) {
			log.Printf("NATS reconnected to %s", nc.ConnectedUrl())
		}),
		nats.ClosedHandler(func(nc *nats.Conn) {
			log.Println("NATS connection closed")
		}),
	}

	conn, err := nats.Connect(cfg.NATSURL, opts...)
	if err != nil {
		return nil, err
	}
	nc.conn = conn

	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, err
	}
	nc.js = js

	return nc, nil
}

func (nc *NATSClient) CreateStream() error {
	_, err := nc.js.StreamInfo("METRICS")
	if err == nil {
		return nil // Stream already exists
	}

	_, err = nc.js.AddStream(&nats.StreamConfig{
		Name:     "METRICS",
		Subjects: []string{"metrics.>"},
		Storage:  nats.FileStorage,
		MaxAge:   24 * time.Hour,
	})
	if err != nil {
		return err
	}

	log.Println("Created METRICS stream")
	return nil
}

func (nc *NATSClient) Publish(agentID string, metrics []models.Metric) error {
	payload := Payload{
		AgentID:   agentID,
		Metrics:   metrics,
		Timestamp: time.Now().UnixMilli(),
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	_, err = nc.js.Publish(nc.subject, data, nats.AckWait(5*time.Second))
	if err != nil {
		if nc.conn.Status() != nats.CONNECTED {
			nc.mu.Lock()
			nc.buffer.Value = data
			nc.buffer = nc.buffer.Next()
			nc.mu.Unlock()
			log.Printf("NATS disconnected, buffered message (%d in buffer)", nc.countBuffer())
			return nil
		}
		return err
	}

	return nil
}

func (nc *NATSClient) countBuffer() int {
	nc.mu.Lock()
	defer nc.mu.Unlock()

	count := 0
	nc.buffer.Do(func(v interface{}) {
		if v != nil {
			count++
		}
	})
	return count
}

func (nc *NATSClient) FlushBuffer() error {
	nc.mu.Lock()
	defer nc.mu.Unlock()

	var failed [][]byte

	nc.buffer.Do(func(v interface{}) {
		if v == nil {
			return
		}
		data := v.([]byte)
		_, err := nc.js.Publish(nc.subject, data, nats.AckWait(5*time.Second))
		if err != nil {
			failed = append(failed, data)
			log.Printf("Failed to flush buffered message: %v", err)
		}
	})

	// Reset buffer with failed messages
	nc.buffer = ring.New(nc.bufferSize)
	for _, data := range failed {
		nc.buffer.Value = data
		nc.buffer = nc.buffer.Next()
	}

	if len(failed) > 0 {
		return nil // Don't return error, keep trying
	}

	return nil
}

func (nc *NATSClient) Close() error {
	if err := nc.FlushBuffer(); err != nil {
		log.Printf("Error flushing buffer: %v", err)
	}

	if nc.conn != nil {
		nc.conn.Drain()
		nc.conn.Close()
	}
	return nil
}

func (nc *NATSClient) IsConnected() bool {
	return nc.conn != nil && nc.conn.Status() == nats.CONNECTED
}
