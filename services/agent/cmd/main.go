package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/awatch/agent/pkg/collector"
	"github.com/awatch/agent/pkg/config"
	"github.com/awatch/agent/pkg/grpc"
	natsclient "github.com/awatch/agent/pkg/nats"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Initialize gRPC client
	grpcClient, err := grpc.NewGRPCClient(cfg)
	if err != nil {
		log.Fatalf("Failed to create gRPC client: %v", err)
	}
	defer grpcClient.Close()

	// Initialize NATS client
	natsClient, err := natsclient.NewNATSClient(cfg)
	if err != nil {
		log.Printf("Warning: Failed to create NATS client: %v", err)
	} else {
		defer natsClient.Close()
		// Create stream if not exists
		if err := natsClient.CreateStream(); err != nil {
			log.Printf("Warning: Failed to create NATS stream: %v", err)
		}
	}

	// Connect to gRPC broker
	if err := grpcClient.Connect(ctx); err != nil {
		log.Printf("Failed to connect to broker: %v", err)
		// Try to reconnect in background
		go func() {
			for {
				select {
				case <-ctx.Done():
					return
				default:
				}
				if err := grpcClient.Connect(ctx); err == nil {
					log.Println("Reconnected to broker")
					break
				}
			}
		}()
	}

	log.Printf("Agent %s started", cfg.AgentID)
	log.Printf("  gRPC broker: %s", cfg.BrokerURL)
	log.Printf("  NATS: %s", cfg.NATSURL)

	// Initialize collector
	col := collector.New()

	// Start collection loop using Run() for batching
	batchChan := col.Run(ctx, cfg.CollectionInterval, cfg.BatchSize)

	// Send batches to broker and NATS
	go func() {
		for batch := range batchChan {
			// Send via gRPC
			if err := grpcClient.SendMetricsBatch(ctx, cfg.AgentID, batch); err != nil {
				log.Printf("Error sending metrics via gRPC: %v", err)
			}

			// Also publish to NATS
			if natsClient != nil {
				if err := natsClient.Publish(cfg.AgentID, batch); err != nil {
					log.Printf("Error publishing to NATS: %v", err)
				}
			}
		}
	}()

	// Wait for shutdown signal
	<-sigChan
	log.Println("Shutting down agent...")
	cancel()
}
