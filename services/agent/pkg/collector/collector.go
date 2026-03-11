package collector

import (
	"context"
	"log"
	"os"
	"sync"
	"time"

	"github.com/awatch/agent/pkg/models"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/mem"
	"github.com/shirou/gopsutil/v3/net"
	"github.com/shirou/gopsutil/v3/process"
)

type Collector struct {
	selfPID            int32
	prevNetCounters    []net.IOCountersStat
	prevDiskCounters   map[string]disk.IOCountersStat
	lastCollectionTime time.Time
	mu                 sync.Mutex
}

func New() *Collector {
	return &Collector{
		selfPID:            int32(os.Getpid()),
		prevNetCounters:    nil,
		prevDiskCounters:   make(map[string]disk.IOCountersStat),
		lastCollectionTime: time.Now(),
	}
}

func (c *Collector) CollectCPU() (float64, error) {
	totalPercent, err := cpu.Percent(0, false)
	if err != nil {
		return 0, err
	}
	if len(totalPercent) == 0 {
		return 0, nil
	}

	proc, err := process.NewProcess(c.selfPID)
	if err != nil {
		return totalPercent[0], nil
	}

	agentPercent, err := proc.CPUPercent()
	if err != nil {
		return totalPercent[0], nil
	}

	result := totalPercent[0] - agentPercent
	if result < 0 {
		result = 0
	}
	if result > 100 {
		result = 100
	}
	return result, nil
}

func (c *Collector) CollectRAM() (used uint64, available uint64, percent float64, err error) {
	sysMem, err := mem.VirtualMemory()
	if err != nil {
		return 0, 0, 0, err
	}

	proc, err := process.NewProcess(c.selfPID)
	if err != nil {
		return sysMem.Used, sysMem.Available, sysMem.UsedPercent, nil
	}

	agentMem, err := proc.MemoryInfo()
	if err != nil {
		return sysMem.Used, sysMem.Available, sysMem.UsedPercent, nil
	}

	adjustedUsed := sysMem.Used - agentMem.RSS
	if adjustedUsed < 0 {
		adjustedUsed = 0
	}

	adjustedPercent := float64(adjustedUsed) / float64(sysMem.Total) * 100

	return adjustedUsed, sysMem.Available, adjustedPercent, nil
}

func (c *Collector) CollectNetwork() (bytesIn uint64, bytesOut uint64, err error) {
	counters, err := net.IOCounters(false)
	if err != nil {
		return 0, 0, err
	}
	if len(counters) == 0 {
		return 0, 0, nil
	}

	current := counters[0]
	bytesIn = current.BytesRecv
	bytesOut = current.BytesSent

	if len(c.prevNetCounters) > 0 {
		prev := c.prevNetCounters[0]
		deltaTime := time.Since(c.lastCollectionTime).Seconds()
		if deltaTime > 0 {
			recvDelta := int64(current.BytesRecv) - int64(prev.BytesRecv)
			sentDelta := int64(current.BytesSent) - int64(prev.BytesSent)
			if recvDelta > 0 {
				bytesIn = uint64(float64(recvDelta) / deltaTime)
			} else {
				bytesIn = 0
			}
			if sentDelta > 0 {
				bytesOut = uint64(float64(sentDelta) / deltaTime)
			} else {
				bytesOut = 0
			}
		}
	}

	c.prevNetCounters = counters
	c.lastCollectionTime = time.Now()

	// Note: agent's own outbound traffic (gRPC/NATS) is negligible at ~1KB/s
	// and does not need subtraction

	return bytesIn, bytesOut, nil
}

func (c *Collector) CollectDisk() (readBytes uint64, writeBytes uint64, err error) {
	counters, err := disk.IOCounters()
	if err != nil {
		return 0, 0, err
	}

	var totalRead, totalWrite uint64
	for name, current := range counters {
		// Exclude loop devices
		if len(name) >= 4 && name[:4] == "loop" {
			continue
		}

		prev, exists := c.prevDiskCounters[name]
		deltaTime := time.Since(c.lastCollectionTime).Seconds()

		if exists && deltaTime > 0 {
			readDelta := int64(current.ReadBytes) - int64(prev.ReadBytes)
			writeDelta := int64(current.WriteBytes) - int64(prev.WriteBytes)
			if readDelta > 0 {
				totalRead += uint64(float64(readDelta) / deltaTime)
			}
			if writeDelta > 0 {
				totalWrite += uint64(float64(writeDelta) / deltaTime)
			}
		}

		c.prevDiskCounters[name] = current
	}

	return totalRead, totalWrite, nil
}

func (c *Collector) CollectAll() ([]models.Metric, error) {
	metrics := []models.Metric{}
	timestamp := time.Now().UnixMilli()

	// Collect CPU
	if cpu, err := c.CollectCPU(); err != nil {
		log.Printf("CPU collection error: %v", err)
	} else {
		metrics = append(metrics, models.Metric{
			Type:      "cpu",
			Value:     cpu,
			Unit:      "percent",
			Timestamp: timestamp,
		})
	}

	// Collect RAM
	if used, available, percent, err := c.CollectRAM(); err != nil {
		log.Printf("RAM collection error: %v", err)
	} else {
		metrics = append(metrics, models.Metric{
			Type:      "ram",
			Value:     percent,
			Unit:      "percent",
			Timestamp: timestamp,
		})
		_ = used
		_ = available
	}

	// Collect Network
	if bytesIn, bytesOut, err := c.CollectNetwork(); err != nil {
		log.Printf("Network collection error: %v", err)
	} else {
		metrics = append(metrics, models.Metric{
			Type:      "network_in",
			Value:     float64(bytesIn),
			Unit:      "bytes_per_sec",
			Timestamp: timestamp,
		})
		metrics = append(metrics, models.Metric{
			Type:      "network_out",
			Value:     float64(bytesOut),
			Unit:      "bytes_per_sec",
			Timestamp: timestamp,
		})
	}

	// Collect Disk
	if readBytes, writeBytes, err := c.CollectDisk(); err != nil {
		log.Printf("Disk collection error: %v", err)
	} else {
		metrics = append(metrics, models.Metric{
			Type:      "disk_read",
			Value:     float64(readBytes),
			Unit:      "bytes_per_sec",
			Timestamp: timestamp,
		})
		metrics = append(metrics, models.Metric{
			Type:      "disk_write",
			Value:     float64(writeBytes),
			Unit:      "bytes_per_sec",
			Timestamp: timestamp,
		})
	}

	return metrics, nil
}

func (c *Collector) Run(ctx context.Context, interval time.Duration, batchSize int) <-chan []models.Metric {
	out := make(chan []models.Metric)
	batch := []models.Metric{}

	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				metrics, err := c.CollectAll()
				if err != nil {
					log.Printf("CollectAll error: %v", err)
					continue
				}
				batch = append(batch, metrics...)

				if len(batch) >= batchSize {
					out <- batch
					batch = []models.Metric{}
				}

			case <-ctx.Done():
				// Flush remaining batch
				if len(batch) > 0 {
					out <- batch
				}
				close(out)
				return
			}
		}
	}()

	return out
}
