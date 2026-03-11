package config

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

type Config struct {
	AgentID            string        `yaml:"agent_id"`
	BrokerURL          string        `yaml:"broker_url"`
	NATSURL            string        `yaml:"nats_url"`
	NATSSubject        string        `yaml:"nats_subject"`
	BufferSize         int           `yaml:"buffer_size"`
	CollectionInterval time.Duration `yaml:"collection_interval"`
	BatchSize          int           `yaml:"batch_size"`
	LogLevel           string        `yaml:"log_level"`
	TLSEnabled         bool          `yaml:"tls_enabled"`
	TLSCertPath        string        `yaml:"tls_cert_path"`
}

func Load() (*Config, error) {
	// Command-line flags (highest priority)
	configPath := flag.String("config", configDefaultPath(), "Path to config file")
	agentID := flag.String("agent-id", "", "Unique identifier for this agent")
	brokerURL := flag.String("broker-url", "", "gRPC broker address (host:port)")
	natsURL := flag.String("nats-url", "", "NATS address (nats://host:port)")
	collectionInterval := flag.Duration("collection-interval", 0, "Interval between metric collections")
	batchSize := flag.Int("batch-size", 0, "Number of metrics to batch before sending")
	logLevel := flag.String("log-level", "", "Log level (debug, info, warn, error)")
	tlsEnabled := flag.Bool("tls-enabled", false, "Enable TLS for gRPC connection")
	tlsCertPath := flag.String("tls-cert-path", "", "Path to TLS certificate file")

	flag.Parse()

	cfg := &Config{
		CollectionInterval: 1 * time.Second,
		BatchSize:          10,
		LogLevel:           "info",
		TLSEnabled:         false,
		NATSSubject:        "metrics.raw",
		BufferSize:         1000,
	}

	// Load from config file (lowest priority)
	if *configPath != "" {
		if data, err := os.ReadFile(*configPath); err == nil {
			if err := parseYAML(data, cfg); err != nil {
				return nil, fmt.Errorf("failed to parse config file %s: %w", *configPath, err)
			}
		}
	}

	// Override with environment variables (medium priority)
	if v := os.Getenv("AWATCH_AGENT_ID"); v != "" {
		cfg.AgentID = v
	}
	if v := os.Getenv("AWATCH_BROKER_URL"); v != "" {
		cfg.BrokerURL = v
	}
	if v := os.Getenv("AWATCH_NATS_URL"); v != "" {
		cfg.NATSURL = v
	}
	if v := os.Getenv("AWATCH_COLLECTION_INTERVAL"); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			cfg.CollectionInterval = d
		}
	}
	if v := os.Getenv("AWATCH_BATCH_SIZE"); v != "" {
		if n := parseInt(v); n > 0 {
			cfg.BatchSize = n
		}
	}
	if v := os.Getenv("AWATCH_LOG_LEVEL"); v != "" {
		cfg.LogLevel = v
	}
	if v := os.Getenv("AWATCH_TLS_ENABLED"); v != "" {
		cfg.TLSEnabled = strings.ToLower(v) == "true" || v == "1"
	}
	if v := os.Getenv("AWATCH_TLS_CERT_PATH"); v != "" {
		cfg.TLSCertPath = v
	}

	// Override with command-line flags (highest priority)
	if *agentID != "" {
		cfg.AgentID = *agentID
	}
	if *brokerURL != "" {
		cfg.BrokerURL = *brokerURL
	}
	if *natsURL != "" {
		cfg.NATSURL = *natsURL
	}
	if *collectionInterval > 0 {
		cfg.CollectionInterval = *collectionInterval
	}
	if *batchSize > 0 {
		cfg.BatchSize = *batchSize
	}
	if *logLevel != "" {
		cfg.LogLevel = *logLevel
	}
	if *tlsEnabled {
		cfg.TLSEnabled = *tlsEnabled
	}
	if *tlsCertPath != "" {
		cfg.TLSCertPath = *tlsCertPath
	}

	// Validate
	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

func configDefaultPath() string {
	if runtime.GOOS == "windows" {
		if exePath, err := os.Executable(); err == nil {
			return filepath.Join(filepath.Dir(exePath), "agent.yaml")
		}
		return "agent.yaml"
	}
	return "/etc/awatch/agent.yaml"
}

func parseYAML(data []byte, cfg *Config) error {
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])

		switch key {
		case "agent_id":
			cfg.AgentID = value
		case "broker_url":
			cfg.BrokerURL = value
		case "nats_url":
			cfg.NATSURL = value
		case "nats_subject":
			cfg.NATSSubject = value
		case "buffer_size":
			if n := parseInt(value); n > 0 {
				cfg.BufferSize = n
			}
		case "collection_interval":
			if d, err := time.ParseDuration(value); err == nil {
				cfg.CollectionInterval = d
			}
		case "batch_size":
			if n := parseInt(value); n > 0 {
				cfg.BatchSize = n
			}
		case "log_level":
			cfg.LogLevel = value
		case "tls_enabled":
			cfg.TLSEnabled = value == "true" || value == "1"
		case "tls_cert_path":
			cfg.TLSCertPath = value
		}
	}
	return nil
}

func (c *Config) Validate() error {
	// agent_id: non-empty, only alphanumeric, -, _, max 64 chars
	if c.AgentID == "" {
		return errors.New("agent_id is required")
	}
	if len(c.AgentID) > 64 {
		return errors.New("agent_id must be at most 64 characters")
	}
	if !regexp.MustCompile(`^[a-zA-Z0-9_-]+$`).MatchString(c.AgentID) {
		return errors.New("agent_id must contain only alphanumeric characters, hyphens, and underscores")
	}

	// broker_url: must be valid host:port
	if c.BrokerURL == "" {
		return errors.New("broker_url is required")
	}
	if !isValidHostPort(c.BrokerURL) {
		return errors.New("broker_url must be a valid host:port")
	}

	// nats_url: must start with nats://
	if c.NATSURL == "" {
		return errors.New("nats_url is required")
	}
	if !strings.HasPrefix(c.NATSURL, "nats://") {
		return errors.New("nats_url must start with nats://")
	}

	// collection_interval: between 100ms and 60s
	if c.CollectionInterval < 100*time.Millisecond || c.CollectionInterval > 60*time.Second {
		return errors.New("collection_interval must be between 100ms and 60s")
	}

	// batch_size: between 1 and 1000
	if c.BatchSize < 1 || c.BatchSize > 1000 {
		return errors.New("batch_size must be between 1 and 1000")
	}

	// log_level: one of debug, info, warn, error
	validLogLevels := map[string]bool{
		"debug": true,
		"info":  true,
		"warn":  true,
		"error": true,
	}
	if !validLogLevels[c.LogLevel] {
		return errors.New("log_level must be one of: debug, info, warn, error")
	}

	// tls_cert_path: required if tls_enabled = true
	if c.TLSEnabled && c.TLSCertPath == "" {
		return errors.New("tls_cert_path is required when tls_enabled is true")
	}
	if c.TLSCertPath != "" {
		if _, err := os.Stat(c.TLSCertPath); os.IsNotExist(err) {
			return fmt.Errorf("tls_cert_path file does not exist: %s", c.TLSCertPath)
		}
	}

	return nil
}

func isValidHostPort(s string) bool {
	parts := strings.Split(s, ":")
	if len(parts) != 2 {
		return false
	}
	host := parts[0]
	port := parts[1]
	if host == "" {
		return false
	}
	if port == "" {
		return false
	}
	// Basic port validation
	for _, c := range port {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func parseInt(s string) int {
	var n int
	fmt.Sscanf(s, "%d", &n)
	return n
}
