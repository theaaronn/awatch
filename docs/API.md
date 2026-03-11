# API Documentation

## gRPC Services

### MetricsService

#### StreamMetrics
Stream de métricas desde el agente al broker.

**Request:** `MetricBatch`
- `agent_id`: string - ID del agente
- `timestamp`: int64 - Timestamp Unix
- `metrics`: array de Metric

**Response:** `StreamAck`
- `success`: bool
- `message`: string

## REST API (AI Worker)

### Health Check
```
GET /health
```

### WebSocket Endpoint
```
WS /ws/alerts
```

Streams anomalías en tiempo real.

## Message Queue (NATS)

### Subjects

- `metrics.raw`: Métricas crudas desde agentes
- `metrics.processed`: Métricas procesadas
- `alerts.anomalies`: Anomalías detectadas
