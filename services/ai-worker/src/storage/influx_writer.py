import asyncio
import logging
from collections import deque
from typing import Dict, List, Optional

from influxdb_client import Point, WritePrecision
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

logger = logging.getLogger(__name__)


class InfluxWriter:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self._client: Optional[InfluxDBClientAsync] = None
        self._write_api = None
        self._query_api = None
        self._buffer: deque = deque(maxlen=10_000)
        self._batch_size = 1000
        self._flush_interval = 5.0
        self._flush_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        self._client = InfluxDBClientAsync(
            url=self.url,
            token=self.token,
            org=self.org,
        )
        self._write_api = self._client.write_api()
        self._query_api = self._client.query_api()
        
        self._flush_task = asyncio.create_task(self._flush_loop())
        
        logger.info(f"Connected to InfluxDB at {self.url}")

    async def write_metric(
        self, agent_id: str, metric_type: str, value: float, timestamp_ms: int
    ) -> None:
        point = (
            Point("metrics")
            .tag("agent_id", agent_id)
            .tag("metric_type", metric_type)
            .field("value", value)
            .time(timestamp_ms, WritePrecision.MILLISECONDS)
        )
        
        self._buffer.append(point)
        
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def write_alert(self, alert: Dict) -> None:
        point = (
            Point("alerts")
            .tag("agent_id", alert["agent_id"])
            .tag("severity", alert["severity"])
            .field("reconstruction_error", float(alert["reconstruction_error"]))
            .field("threshold", float(alert["threshold"]))
            .field("confidence", float(alert["confidence"]))
            .field("message", str(alert["message"]))
            .time(alert["timestamp"], WritePrecision.MILLISECONDS)
        )
        
        await self._write_api.write(
            bucket=self.bucket, org=self.org, record=point
        )
        logger.debug(f"Wrote alert for agent {alert['agent_id']}")

    async def _flush(self) -> None:
        if not self._buffer:
            return
        
        points_to_write = []
        for _ in range(min(self._batch_size, len(self._buffer))):
            if self._buffer:
                points_to_write.append(self._buffer.popleft())
        
        if not points_to_write:
            return
        
        try:
            await self._write_api.write(
                bucket=self.bucket, org=self.org, record=points_to_write
            )
            logger.debug(f"Flushed {len(points_to_write)} points to InfluxDB")
        except Exception as e:
            logger.error(f"Failed to flush points: {e}")
            for point in reversed(points_to_write):
                if len(self._buffer) < self._buffer.maxlen:
                    self._buffer.appendleft(point)

    async def _flush_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                if len(self._buffer) > 0:
                    await self._flush()
            except asyncio.CancelledError:
                logger.info("Flush loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def query_metrics(
        self, agent_id: str, metric_type: str, start: str = "-1h"
    ) -> List[Dict]:
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start})
          |> filter(fn: (r) => r._measurement == "metrics")
          |> filter(fn: (r) => r.agent_id == "{agent_id}")
          |> filter(fn: (r) => r.metric_type == "{metric_type}")
          |> filter(fn: (r) => r._field == "value")
          |> sort(columns: ["_time"])
        '''
        
        tables = await self._query_api.query(query, org=self.org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "timestamp": int(record.get_time().timestamp() * 1000),
                    "value": record.get_value(),
                })
        
        return results

    async def query_alerts(self, agent_id: str, start: str = "-24h") -> List[Dict]:
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start})
          |> filter(fn: (r) => r._measurement == "alerts")
          |> filter(fn: (r) => r.agent_id == "{agent_id}")
          |> sort(columns: ["_time"])
        '''
        
        tables = await self._query_api.query(query, org=self.org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "timestamp": int(record.get_time().timestamp() * 1000),
                    "reconstruction_error": record.values.get("reconstruction_error"),
                    "threshold": record.values.get("threshold"),
                    "confidence": record.values.get("confidence"),
                    "severity": record.values.get("severity"),
                    "message": record.values.get("message"),
                })
        
        return results

    async def setup_buckets(self) -> None:
        # Buckets are provisioned by Docker's INFLUXDB init env vars.
        # Just verify connectivity here.
        try:
            await self._client.ping()
            logger.info("InfluxDB ping successful")
        except Exception as e:
            logger.error(f"InfluxDB ping failed: {e}")

    async def is_connected(self) -> bool:
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        if len(self._buffer) > 0:
            await self._flush()
        
        if self._client:
            await self._client.close()
        
        logger.info("InfluxDB connection closed")

    async def write_batch_metrics(
        self, agent_id: str, metrics: List[Dict]
    ) -> None:
        for metric in metrics:
            await self.write_metric(
                agent_id=agent_id,
                metric_type=metric.get("type", "unknown"),
                value=metric.get("value", 0.0),
                timestamp_ms=metric.get("timestamp", 0),
            )

    async def query_training_data(
        self, agent_id: str, hours: int = 24
    ) -> List[Dict]:
        start = f"-{hours}h"
        
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start})
          |> filter(fn: (r) => r._measurement == "metrics")
          |> filter(fn: (r) => r.agent_id == "{agent_id}")
          |> filter(fn: (r) => r._field == "value")
          |> pivot(rowKey:["_time"], columnKey: ["metric_type"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        
        tables = await self._query_api.query(query, org=self.org)
        
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "timestamp": int(record.get_time().timestamp() * 1000),
                    "cpu": record.values.get("cpu", 0.0),
                    "ram": record.values.get("ram", 0.0),
                    "network_in": record.values.get("network_in", 0.0),
                    "network_out": record.values.get("network_out", 0.0),
                    "disk_read": record.values.get("disk_read", 0.0),
                    "disk_write": record.values.get("disk_write", 0.0),
                })
        
        return results
