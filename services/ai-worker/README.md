# Python AI Worker

Servicio de detección de anomalías usando Autoencoders con PyTorch.

## Estructura

```
ai-worker/
├── app/              # FastAPI application
│   ├── __init__.py
│   ├── main.py       # Entry point
│   └── api/
│       ├── __init__.py
│       └── routes.py
├── models/           # Modelos entrenados (.pth)
├── src/
│   ├── autoencoder/  # Implementación del AE
│   │   ├── __init__.py
│   │   ├── model.py
│   │   └── trainer.py
│   ├── api/          # Clientes API
│   │   ├── __init__.py
│   │   └── nats_client.py
│   └── config/       # Configuración
│       ├── __init__.py
│       └── settings.py
├── tests/            # Tests unitarios
├── requirements.txt  # Dependencias
└── Dockerfile
```

## Variables de Entorno

- `NATS_URL`: URL del servidor NATS
- `MODEL_PATH`: Ruta al modelo entrenado
- `THRESHOLD`: Umbral de detección de anomalías
- `INFLUXDB_URL`: URL de InfluxDB
