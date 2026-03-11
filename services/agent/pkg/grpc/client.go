package grpc

import (
	"context"
	"fmt"
	"io"
	"log"
	"sync"
	"time"

	"github.com/awatch/agent/pkg/config"
	"github.com/awatch/agent/pkg/models"
	pb "github.com/awatch/agent/pkg/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/encoding/gzip"
	"google.golang.org/grpc/keepalive"
)

type GRPCClient struct {
	conn          *grpc.ClientConn
	client        pb.MetricsServiceClient
	stream        pb.MetricsService_StreamMetricsClient
	mu            sync.Mutex
	isConnected   bool
	config        *config.Config
	ctx           context.Context
	cancel        context.CancelFunc
	batchSequence uint64
}

func NewGRPCClient(cfg *config.Config) (*GRPCClient, error) {
	ctx, cancel := context.WithCancel(context.Background())

	return &GRPCClient{
		config:        cfg,
		ctx:           ctx,
		cancel:        cancel,
		batchSequence: 0,
	}, nil
}

func (c *GRPCClient) Connect(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.isConnected {
		return nil
	}

	opts := []grpc.DialOption{
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:    30 * time.Second,
			Timeout: 10 * time.Second,
		}),
		grpc.WithDefaultCallOptions(grpc.UseCompressor(gzip.Name)),
		grpc.WithTimeout(10 * time.Second),
	}

	if c.config.TLSEnabled {
		creds, err := credentials.NewClientTLSFromFile(c.config.TLSCertPath, "")
		if err != nil {
			return fmt.Errorf("failed to load TLS cert: %w", err)
		}
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	conn, err := grpc.DialContext(ctx, c.config.BrokerURL, opts...)
	if err != nil {
		return fmt.Errorf("failed to connect to broker: %w", err)
	}

	c.conn = conn
	c.client = pb.NewMetricsServiceClient(conn)

	stream, err := c.client.StreamMetrics(ctx)
	if err != nil {
		conn.Close()
		return fmt.Errorf("failed to start streaming: %w", err)
	}

	c.stream = stream
	c.isConnected = true
	go c.handleAcks()

	log.Printf("Connected to broker at %s", c.config.BrokerURL)
	return nil
}

func (c *GRPCClient) SendBatch(batch *pb.MetricBatch) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.isConnected || c.stream == nil {
		return fmt.Errorf("not connected")
	}

	err := c.stream.Send(batch)
	if err != nil {
		c.isConnected = false
		return fmt.Errorf("failed to send batch: %w", err)
	}
	return nil
}

func (c *GRPCClient) SendMetricsBatch(ctx context.Context, agentID string, metricsList []models.Metric) error {
	c.mu.Lock()
	c.batchSequence++
	seq := c.batchSequence
	c.mu.Unlock()

	batch := &pb.MetricBatch{
		AgentId:       agentID,
		CollectedAt:   time.Now().UnixMilli(),
		BatchSequence: seq,
		Metrics:       make([]*pb.Metric, len(metricsList)),
	}

	for i, m := range metricsList {
		batch.Metrics[i] = &pb.Metric{
			MetricType: m.Type,
			Value:      m.Value,
			Unit:       m.Unit,
			Timestamp:  m.Timestamp,
		}
	}

	maxRetries := 3
	backoffs := []time.Duration{100 * time.Millisecond, 500 * time.Millisecond, 2 * time.Second}

	for attempt := 0; attempt < maxRetries; attempt++ {
		err := c.SendBatch(batch)
		if err == nil {
			return nil
		}
		log.Printf("SendBatch attempt %d failed: %v", attempt+1, err)
		if !c.IsConnected() {
			reconnectErr := c.Reconnect(ctx)
			if reconnectErr != nil {
				log.Printf("Reconnect failed: %v", reconnectErr)
			}
		}
		if attempt < len(backoffs) {
			time.Sleep(backoffs[attempt])
		}
	}
	return fmt.Errorf("failed after %d retries", maxRetries)
}

func (c *GRPCClient) handleAcks() {
	for {
		select {
		case <-c.ctx.Done():
			return
		default:
		}
		ack, err := c.stream.Recv()
		if err != nil {
			if err == io.EOF || c.ctx.Err() != nil {
				log.Println("Stream closed by server")
			} else {
				log.Printf("Error receiving ack: %v", err)
			}
			c.mu.Lock()
			c.isConnected = false
			c.mu.Unlock()
			return
		}
		if ack.Success {
			log.Printf("Batch %d acknowledged: %s", ack.BatchSequence, ack.Message)
		} else {
			log.Printf("Batch %d failed: %s", ack.BatchSequence, ack.Message)
		}
	}
}

func (c *GRPCClient) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.cancel()
	if c.stream != nil {
		c.stream.CloseSend()
	}
	if c.conn != nil {
		err := c.conn.Close()
		c.isConnected = false
		return err
	}
	return nil
}

func (c *GRPCClient) Reconnect(ctx context.Context) error {
	c.mu.Lock()
	if c.conn != nil {
		c.conn.Close()
	}
	c.isConnected = false
	c.stream = nil
	c.mu.Unlock()

	backoffs := []time.Duration{1 * time.Second, 2 * time.Second, 4 * time.Second, 8 * time.Second, 16 * time.Second}

	for _, backoff := range backoffs {
		log.Printf("Reconnecting in %v...", backoff)
		select {
		case <-ctx.Done():
			return fmt.Errorf("reconnect cancelled")
		case <-time.After(backoff):
		}

		err := c.Connect(ctx)
		if err == nil {
			log.Println("Reconnected successfully")
			return nil
		}
		log.Printf("Reconnect attempt failed: %v", err)
	}
	return fmt.Errorf("failed to reconnect after %d attempts", len(backoffs))
}

func (c *GRPCClient) IsConnected() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.isConnected
}
