# Agente Awatch (Go)

Agente recolector de métricas ligero escrito en Go.

## Características

- Recolección cada segundo de:
  - CPU usage (%)
  - Memory usage (%)
  - Network I/O (bytes)
- Comunicación gRPC con el broker
- Binario nativo, bajo consumo de recursos

## Uso

```bash
go run cmd/main.go
```

## Variables de Entorno

- `AGENT_ID`: Identificador único del agente
- `BROKER_URL`: URL del servidor gRPC (ej: localhost:50051)
- `COLLECTION_INTERVAL`: Intervalo de recolección (default: 1s)

## Build

```bash
go build -o agent cmd/main.go
```
