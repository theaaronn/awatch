import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.api.nats_client import NATSConsumer
from src.api.stats import stats
from src.api.websocket import manager as ws_manager
from src.config.settings import settings
from src.detector.inference import AnomalyDetector
from src.storage.influx_writer import InfluxWriter
from src.storage.postgres import PostgresClient
from src.training.training_manager import TrainingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

consumer: Optional[NATSConsumer] = None
influx_client: Optional[InfluxWriter] = None
postgres_client: Optional[PostgresClient] = None
detector: Optional[AnomalyDetector] = None
training_manager: Optional[TrainingManager] = None
processing_task: Optional[asyncio.Task] = None


async def process_metric_batch(message: Dict) -> None:
    start_time = time.time()
    
    agent_id = message.get("agent_id", "unknown")
    metrics_list = message.get("metrics", [])
    timestamp = message.get("timestamp", int(time.time() * 1000))
    
    logger.debug(f"Processing {len(metrics_list)} metrics from agent {agent_id}")
    
    for metric in metrics_list:
        try:
            await influx_client.write_metric(
                agent_id=agent_id,
                metric_type=metric.get("type", "unknown"),
                value=metric.get("value", 0.0),
                timestamp_ms=metric.get("timestamp", timestamp),
            )
        except Exception as e:
            logger.error(f"Failed to write metric to InfluxDB: {e}")
    
    if detector and metrics_list:
        metrics_dict = {
            "cpu": next((m["value"] for m in metrics_list if m.get("type") == "cpu"), 0.0),
            "ram": next((m["value"] for m in metrics_list if m.get("type") == "ram"), 0.0),
            "network_in": next((m["value"] for m in metrics_list if m.get("type") == "network_in"), 0.0),
            "network_out": next((m["value"] for m in metrics_list if m.get("type") == "network_out"), 0.0),
            "disk_read": next((m["value"] for m in metrics_list if m.get("type") == "disk_read"), 0.0),
            "disk_write": next((m["value"] for m in metrics_list if m.get("type") == "disk_write"), 0.0),
            "timestamp": timestamp,
        }
        
        try:
            anomaly = detector.detect_anomaly(agent_id, metrics_dict)
            
            if anomaly:
                stats.record_anomaly_detected()
                
                await influx_client.write_alert(anomaly)
                
                await ws_manager.send_alert(anomaly)
                
                server = await postgres_client.get_server_by_agent_id(agent_id)
                if server:
                    incident = await postgres_client.create_incident(
                        server_id=server.id,
                        severity=anomaly["severity"],
                        reconstruction_error=anomaly["reconstruction_error"],
                        threshold=anomaly["threshold"],
                        confidence=anomaly["confidence"],
                        affected_metrics=anomaly["affected_metrics"],
                        message=anomaly["message"],
                    )
                    logger.info(f"Incident created: {incident.id}")
                    
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
    
    latency = (time.time() - start_time) * 1000
    stats.record_message_processed(latency)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, influx_client, postgres_client, detector, training_manager, processing_task
    
    logger.info("Starting AI Worker...")
    
    influx_client = InfluxWriter(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
        bucket=settings.influxdb_bucket,
    )
    
    try:
        await influx_client.connect()
        await influx_client.setup_buckets()
        logger.info("InfluxDB connected")
    except Exception as e:
        logger.error(f"InfluxDB connection failed: {e}")
    
    postgres_client = PostgresClient(database_url=settings.postgres_url)
    
    try:
        await postgres_client.create_tables()
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
    
    consumer = NATSConsumer(
        nats_url=settings.nats_url,
        subject="metrics.raw",
        durable_name="ai-worker-consumer",
    )
    
    try:
        await consumer.connect()
    except Exception as e:
        logger.error(f"NATS connection failed: {e}")

    try:
        await consumer.setup_stream()
    except Exception as e:
        logger.warning(f"NATS stream setup warning: {e}")

    try:
        await consumer.create_subscription()
        logger.info("NATS connected and subscription created")
    except Exception as e:
        logger.error(f"NATS subscription failed: {e}")
    
    try:
        detector = AnomalyDetector(model_path=settings.model_path)
        logger.info("Anomaly detector loaded")
    except Exception as e:
        logger.warning(f"Anomaly detector not loaded: {e}")
        detector = None
    
    training_manager = TrainingManager(
        influx_client=influx_client,
        postgres_client=postgres_client,
        model_path=settings.model_path,
    )
    
    ws_manager.set_api_keys(settings.websocket_api_keys)
    logger.info(f"WebSocket manager initialized with {len(settings.websocket_api_keys)} API keys")
    
    if consumer and consumer.sub:
        processing_task = asyncio.create_task(
            consumer.process_messages(process_metric_batch)
        )
        logger.info("Message processing started")
    
    logger.info("All services initialized")
    yield
    
    logger.info("Shutting down AI Worker service...")
    
    if processing_task:
        processing_task.cancel()
        try:
            await processing_task
        except asyncio.CancelledError:
            pass
    
    if consumer:
        await consumer.close()
    
    if influx_client:
        await influx_client.close()
    
    if postgres_client:
        await postgres_client.close()
    
    logger.info("Shutdown complete")


app = FastAPI(
    title="Awatch AI Worker API",
    description="Anomaly detection and ML inference service",
    version="1.0.0",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
        },
    )


@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    nats_connected = consumer.nc is not None if consumer else False
    influx_connected = await influx_client.is_connected() if influx_client else False
    model_loaded = detector is not None and detector.model is not None
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": int(time.time()),
        "services": {
            "nats": "connected" if nats_connected else "disconnected",
            "influxdb": "connected" if influx_connected else "disconnected",
            "model": "loaded" if model_loaded else "not_loaded",
        },
    }


@app.get("/metrics/stats")
@limiter.limit("100/minute")
async def get_metrics_stats(request: Request):
    queue_depth = 0
    if consumer:
        queue_depth = await consumer.get_pending_count()
    
    return {
        "total_processed": stats.total_messages_processed,
        "total_anomalies": stats.total_anomalies_detected,
        "processing_rate": stats.messages_per_second,
        "avg_latency_ms": stats.avg_processing_latency_ms,
        "last_update": stats.last_update_timestamp,
        "queue_depth": queue_depth,
    }


@app.get("/metrics")
@limiter.limit("100/minute")
async def get_metrics(
    request: Request,
    agent_id: str = Query(..., description="Agent ID to query metrics for"),
    metric_type: str = Query(..., description="Metric type: cpu, ram, network_in, network_out, disk_read, disk_write"),
    start: str = Query("-1h", description="Time range: -1h, -6h, -24h, -7d"),
):
    if not influx_client:
        raise HTTPException(status_code=503, detail="InfluxDB not connected")
    
    valid_metric_types = ["cpu", "ram", "network_in", "network_out", "disk_read", "disk_write"]
    if metric_type not in valid_metric_types:
        raise HTTPException(status_code=400, detail=f"Invalid metric_type. Must be one of: {valid_metric_types}")
    
    valid_starts = ["-1h", "-6h", "-24h", "-7d"]
    if start not in valid_starts:
        raise HTTPException(status_code=400, detail=f"Invalid start. Must be one of: {valid_starts}")
    
    try:
        data = await influx_client.query_metrics(
            agent_id=agent_id,
            metric_type=metric_type,
            start=start,
        )
        return data
    except Exception as e:
        logger.error(f"Failed to query metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TrainRequest(BaseModel):
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    agent_id: Optional[str] = None


@app.post("/model/train")
@limiter.limit("10/hour")
async def trigger_training(request: Request, train_req: TrainRequest):
    if not training_manager:
        raise HTTPException(status_code=503, detail="Training manager not initialized")
    
    try:
        task_id = await training_manager.start_training(
            agent_id=train_req.agent_id,
            hours=168,
        )
        return {
            "status": "training_started",
            "task_id": task_id,
            "message": "Model training initiated in background",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model/status")
@limiter.limit("100/minute")
async def get_model_status(request: Request):
    if not detector:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    total_params = sum(p.numel() for p in detector.model.parameters())
    
    return {
        "model_version": detector.model_version,
        "trained_at": detector.model_trained_at.isoformat() if detector.model_trained_at else None,
        "training_samples": detector.training_sample_count,
        "threshold": detector.threshold,
        "architecture": {
            "input_dim": detector.model.input_dim,
            "encoding_dims": detector.model.encoding_dims,
            "total_params": total_params,
        },
        "performance": {
            "avg_inference_time_ms": stats.avg_inference_time_ms,
            "throughput": stats.inference_throughput,
        },
    }


@app.get("/servers")
@limiter.limit("100/minute")
async def get_servers_list(request: Request):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    servers = await postgres_client.get_servers()
    return [
        {
            "id": str(s.id),
            "agent_id": s.agent_id,
            "hostname": s.hostname,
            "ip_address": s.ip_address,
            "status": s.status,
            "agent_version": s.agent_version,
            "last_seen": s.last_seen.isoformat() if s.last_seen else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in servers
    ]


class ServerCreateRequest(BaseModel):
    agent_id: str
    hostname: str
    ip_address: str


@app.post("/servers")
@limiter.limit("100/minute")
async def create_server(request: Request, server_req: ServerCreateRequest):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', server_req.agent_id):
        raise HTTPException(status_code=400, detail="agent_id must match ^[a-zA-Z0-9_-]{1,64}$")
    
    existing = await postgres_client.get_server_by_agent_id(server_req.agent_id)
    if existing:
        raise HTTPException(status_code=409, detail="An agent with this ID already exists")
    
    server = await postgres_client.upsert_server(
        agent_id=server_req.agent_id,
        hostname=server_req.hostname,
        ip_address=server_req.ip_address,
    )
    server.status = "offline"
    
    return {
        "id": str(server.id),
        "agent_id": server.agent_id,
        "hostname": server.hostname,
        "ip_address": server.ip_address,
        "status": server.status,
        "agent_version": server.agent_version,
        "last_seen": server.last_seen.isoformat() if server.last_seen else None,
        "created_at": server.created_at.isoformat(),
    }


@app.delete("/servers/{agent_id}")
@limiter.limit("100/minute")
async def delete_server(request: Request, agent_id: str):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    deleted = await postgres_client.delete_server(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    
    return {"status": "deleted"}


@app.get("/incidents")
@limiter.limit("100/minute")
async def get_incidents_list(
    request: Request,
    server_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    limit = min(limit, 200)
    
    import uuid as uuid_module
    server_uuid = None
    if server_id:
        try:
            server_uuid = uuid_module.UUID(server_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid server_id format")
    
    incidents = await postgres_client.get_incidents(
        server_id=server_uuid,
        status=status,
        limit=limit,
        offset=offset,
    )
    
    total = len(incidents) if offset == 0 and len(incidents) < limit else len(incidents)
    
    items = []
    for inc in incidents:
        server = await postgres_client.get_server_by_id(inc.server_id)
        items.append({
            "id": str(inc.id),
            "server_id": str(inc.server_id),
            "agent_id": server.agent_id if server else "unknown",
            "severity": inc.severity,
            "status": inc.status,
            "reconstruction_error": inc.reconstruction_error,
            "threshold": inc.threshold,
            "confidence": inc.confidence,
            "affected_metrics": inc.affected_metrics.split(",") if inc.affected_metrics else [],
            "message": inc.message,
            "acknowledged_by": str(inc.acknowledged_by) if inc.acknowledged_by else None,
            "acknowledged_at": inc.acknowledged_at.isoformat() if inc.acknowledged_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "created_at": inc.created_at.isoformat(),
        })
    
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.post("/incidents/{incident_id}/acknowledge")
@limiter.limit("100/minute")
async def acknowledge_incident(request: Request, incident_id: str):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    import uuid as uuid_module
    try:
        inc_uuid = uuid_module.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_id format")
    
    user_uuid = uuid_module.uuid4()
    inc = await postgres_client.acknowledge_incident(inc_uuid, user_uuid)
    
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    server = await postgres_client.get_server_by_id(inc.server_id)
    
    return {
        "id": str(inc.id),
        "server_id": str(inc.server_id),
        "agent_id": server.agent_id if server else "unknown",
        "severity": inc.severity,
        "status": inc.status,
        "reconstruction_error": inc.reconstruction_error,
        "threshold": inc.threshold,
        "confidence": inc.confidence,
        "affected_metrics": inc.affected_metrics.split(",") if inc.affected_metrics else [],
        "message": inc.message,
        "acknowledged_by": str(inc.acknowledged_by) if inc.acknowledged_by else None,
        "acknowledged_at": inc.acknowledged_at.isoformat() if inc.acknowledged_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "created_at": inc.created_at.isoformat(),
    }


@app.post("/incidents/{incident_id}/resolve")
@limiter.limit("100/minute")
async def resolve_incident(request: Request, incident_id: str):
    if not postgres_client:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    import uuid as uuid_module
    try:
        inc_uuid = uuid_module.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_id format")
    
    inc = await postgres_client.resolve_incident(inc_uuid)
    
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    server = await postgres_client.get_server_by_id(inc.server_id)
    
    return {
        "id": str(inc.id),
        "server_id": str(inc.server_id),
        "agent_id": server.agent_id if server else "unknown",
        "severity": inc.severity,
        "status": inc.status,
        "reconstruction_error": inc.reconstruction_error,
        "threshold": inc.threshold,
        "confidence": inc.confidence,
        "affected_metrics": inc.affected_metrics.split(",") if inc.affected_metrics else [],
        "message": inc.message,
        "acknowledged_by": str(inc.acknowledged_by) if inc.acknowledged_by else None,
        "acknowledged_at": inc.acknowledged_at.isoformat() if inc.acknowledged_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "created_at": inc.created_at.isoformat(),
    }


@app.websocket("/ws/alerts")
async def websocket_alerts(
    websocket: WebSocket,
    api_key: str = Query(..., description="API key for authentication"),
):
    client_id = str(uuid.uuid4())
    connected = await ws_manager.connect(client_id, websocket, api_key)
    
    if not connected:
        return
    
    logger.info(f"Client {client_id} connected to WebSocket")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            if data == "pong":
                continue
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        ws_manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
