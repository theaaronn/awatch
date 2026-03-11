import time
from dataclasses import dataclass, field
from typing import Dict, List
from collections import deque
import threading


@dataclass
class StatsTracker:
    total_messages_processed: int = 0
    total_anomalies_detected: int = 0
    total_predictions_made: int = 0
    processing_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    inference_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_update_timestamp: float = 0.0
    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_message_processed(self, latency_ms: float) -> None:
        with self._lock:
            self.total_messages_processed += 1
            self.processing_latencies.append(latency_ms)
            self.last_update_timestamp = time.time()

    def record_anomaly_detected(self) -> None:
        with self._lock:
            self.total_anomalies_detected += 1

    def record_prediction(self, inference_time_ms: float) -> None:
        with self._lock:
            self.total_predictions_made += 1
            self.inference_times.append(inference_time_ms)

    @property
    def messages_per_second(self) -> float:
        with self._lock:
            elapsed = time.time() - self.start_time
            if elapsed <= 0:
                return 0.0
            return self.total_messages_processed / elapsed

    @property
    def avg_processing_latency_ms(self) -> float:
        with self._lock:
            if not self.processing_latencies:
                return 0.0
            return sum(self.processing_latencies) / len(self.processing_latencies)

    @property
    def avg_inference_time_ms(self) -> float:
        with self._lock:
            if not self.inference_times:
                return 0.0
            return sum(self.inference_times) / len(self.inference_times)

    @property
    def inference_throughput(self) -> float:
        with self._lock:
            elapsed = time.time() - self.start_time
            if elapsed <= 0:
                return 0.0
            return self.total_predictions_made / elapsed

    def to_dict(self) -> Dict:
        return {
            "total_processed": self.total_messages_processed,
            "total_anomalies": self.total_anomalies_detected,
            "total_predictions": self.total_predictions_made,
            "processing_rate": round(self.messages_per_second, 2),
            "avg_latency_ms": round(self.avg_processing_latency_ms, 2),
            "avg_inference_time_ms": round(self.avg_inference_time_ms, 2),
            "inference_throughput": round(self.inference_throughput, 2),
            "last_update": self.last_update_timestamp,
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }

    def reset(self) -> None:
        with self._lock:
            self.total_messages_processed = 0
            self.total_anomalies_detected = 0
            self.total_predictions_made = 0
            self.processing_latencies.clear()
            self.inference_times.clear()
            self.last_update_timestamp = 0.0
            self.start_time = time.time()


stats = StatsTracker()
