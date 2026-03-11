# Arquitectura Awatch

## Visión General

Awatch es un sistema de monitoreo distribuido con detección de anomalías basada en IA.

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              NODO A (Agente)                            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │  Collector  │────▶│   gRPC      │────▶│    NATS     │               │
│  │   (Go)      │     │   Client    │     │   Client    │               │
│  └─────────────┘     └─────────────┘     └──────┬──────┘               │
└─────────────────────────────────────────────────┼───────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              NODO B (Broker)                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                          NATS JetStream                           │   │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐         │   │
│  │  │ metrics.raw │────▶│  Consumer   │────▶│ metrics.ia  │         │   │
│  │  └─────────────┘     └─────────────┘     └──────┬──────┘         │   │
│  └─────────────────────────────────────────────────┼────────────────┘   │
│                                                    │                     │
│  ┌─────────────────────────────────────────────────┼────────────────┐   │
│  │              InfluxDB (Time Series)              │                 │   │
│  │  ┌─────────────┐     ┌─────────────┐            │                 │   │
│  │  │   metrics   │     │   alerts    │◄───────────┘                 │   │
│  │  └─────────────┘     └─────────────┘                              │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │            PostgreSQL (Metadata)                                 │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐             │    │
│  │  │  users  │  │ configs │  │ incidents│  │ servers │             │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           NODO C (Worker IA)                            │
│  ┌─────────────┐     ┌─────────────────────────────────────────────┐   │
│  │   NATS      │────▶│              Autoencoder                     │   │
│  │   Consumer  │     │  ┌─────────┐  ┌─────────┐  ┌─────────┐      │   │
│  └─────────────┘     │  │ Encoder │─▶│  Latent │─▶│ Decoder │      │   │
│                      │  │ (input) │   │ (bottleneck)  │ (output)│      │   │
│  ┌─────────────┐     │  └─────────┘  └─────────┘  └─────────┘      │   │
│  │   InfluxDB  │◀────│           Reconstruction Error              │   │
│  │   Writer    │     │              │                              │   │
│  └─────────────┘     │              ▼                              │   │
│                      │        Anomaly? ──▶ Alert!                  │   │
│  ┌─────────────┐     └─────────────────────────────────────────────┘   │
│  │  WebSocket  │────────────────────────────────────────▶              │
│  │   Server    │                                                        │
│  └─────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Dashboard (Frontend)                            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   React     │────▶│   Grafana   │     │   Alerts    │               │
│  │  Dashboard  │     │   Embedded  │     │   Panel     │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│         ▲                                                              │
│         │                                                              │
│    WebSocket                                                           │
│    (Real-time)                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Flujo de Datos

1. **Nodo A**: El agente Go recolecta métricas cada segundo (CPU, RAM, Network)
2. **gRPC**: Envía métricas al broker de forma eficiente (streaming binario)
3. **Nodo B**: NATS JetStream encola los mensajes y persiste en InfluxDB
4. **Nodo C**: El worker Python consume mensajes, aplica el Autoencoder y detecta anomalías
5. **Alertas**: Las anomalías se guardan en InfluxDB y se envían vía WebSocket al dashboard

## Componentes Detallados

### Agente (Go)
- **Responsabilidad**: Recolección ligera de métricas
- **Tecnologías**: gopsutil, gRPC, NATS
- **Distribución**: Instalado en cada servidor objetivo

### Broker (NATS + DBs)
- **Responsabilidad**: Encolamiento y persistencia
- **Tecnologías**: NATS JetStream, InfluxDB, PostgreSQL
- **Distribución**: Servidor central de mensajería

### Worker IA (Python)
- **Responsabilidad**: Detección de anomalías
- **Tecnologías**: PyTorch, FastAPI, WebSockets
- **Distribución**: Servidor dedicado de ML

### Dashboard (React)
- **Responsabilidad**: Visualización y alertas
- **Tecnologías**: React, TypeScript, WebSockets
- **Distribución**: Servidor de frontend

## Justificación Técnica

### gRPC vs REST
- **gRPC**: Streaming bidireccional, binario (más rápido), tipado fuerte
- **Justificación**: Necesitamos streaming continuo de métricas con baja latencia

### NATS JetStream vs RabbitMQ
- **NATS**: Más moderno, integrado con Go, JetStream para persistencia
- **Justificación**: Stack moderno y simple, buen soporte para Go

### Autoencoder vs Umbrales Estáticos
- **AE**: Detecta patrones multidimensionales complejos
- **Justificación**: CPU baja + Disco alto = Anomalía que umbrales simples ignoran

## Escalabilidad

- **Horizontal**: Múltiples agentes, múltiples workers IA
- **Vertical**: Aumentar recursos en cada nodo
- **Particionamiento**: Sharding por agent_id en NATS
