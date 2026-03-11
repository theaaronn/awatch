import logging
import pickle
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from ..autoencoder.model import Autoencoder

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(
        self,
        model_path: str,
        threshold_multiplier: float = 3.0,
        window_size: int = 10,
        suppression_window: int = 300,
    ):
        self.model_path = model_path
        self.threshold_multiplier = threshold_multiplier
        self.window_size = window_size
        self.suppression_window = suppression_window
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._load_model()
        self.model.eval()
        
        self.scaler = self._load_scaler()
        self.baseline_errors = self._load_baseline_errors()
        self.threshold = self._compute_threshold()
        
        self.model_version = "1.0.0"
        self.model_trained_at: Optional[datetime] = None
        self.training_sample_count = 0
        
        self._load_metadata()
        
        self.error_windows: Dict[str, deque] = {}
        self.last_anomaly_time: Dict[str, float] = {}
        
        logger.info(f"AnomalyDetector initialized on {self.device}")
        logger.info(f"Threshold: {self.threshold:.6f} (multiplier={threshold_multiplier})")

    def _load_model(self) -> Autoencoder:
        return Autoencoder.load_model(self.model_path, device=str(self.device))

    def _load_scaler(self):
        scaler_path = Path(self.model_path).parent / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                return pickle.load(f)
        raise FileNotFoundError(f"Scaler not found at {scaler_path}")

    def _load_baseline_errors(self) -> np.ndarray:
        baseline_path = Path(self.model_path).parent / "baseline.npy"
        if baseline_path.exists():
            return np.load(str(baseline_path))
        raise FileNotFoundError(f"Baseline errors not found at {baseline_path}")

    def _load_metadata(self) -> None:
        metadata_path = Path(self.model_path).parent / "training_history.json"
        if metadata_path.exists():
            import json
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            self.training_sample_count = metadata.get("training_samples", 0)
            if "trained_at" in metadata:
                self.model_trained_at = datetime.fromisoformat(metadata["trained_at"])

    def _compute_threshold(self) -> float:
        mean = np.mean(self.baseline_errors)
        std = np.std(self.baseline_errors)
        threshold = mean + self.threshold_multiplier * std
        return float(threshold)

    def normalize(self, metrics: np.ndarray) -> np.ndarray:
        return self.scaler.transform(metrics)

    def denormalize(self, metrics: np.ndarray) -> np.ndarray:
        return self.scaler.inverse_transform(metrics)

    def predict(
        self, metrics: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        normalized = self.normalize(metrics)
        tensor = torch.tensor(normalized, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            reconstructed = self.model(tensor)
            errors = torch.mean((tensor - reconstructed) ** 2, dim=1)
        
        reconstructed_np = reconstructed.cpu().numpy()
        errors_np = errors.cpu().numpy()
        
        return reconstructed_np, errors_np

    def detect_anomaly(
        self, agent_id: str, metrics: Dict
    ) -> Optional[Dict]:
        feature_vector = np.array([[
            metrics.get("cpu", 0.0),
            metrics.get("ram", 0.0),
            metrics.get("network_in", 0.0) + metrics.get("network_out", 0.0),
            metrics.get("disk_read", 0.0) + metrics.get("disk_write", 0.0),
        ]], dtype=np.float32)
        
        _, errors = self.predict(feature_vector)
        error = float(errors[0])
        
        if agent_id not in self.error_windows:
            self.error_windows[agent_id] = deque(maxlen=self.window_size)
        
        self.error_windows[agent_id].append(error)
        
        smoothed_error = np.mean(list(self.error_windows[agent_id]))
        
        if smoothed_error <= self.threshold:
            return None
        
        current_time = datetime.now(timezone.utc).timestamp()
        last_anomaly = self.last_anomaly_time.get(agent_id, 0)
        
        if current_time - last_anomaly < self.suppression_window:
            logger.debug(f"Anomaly suppressed for agent {agent_id} (within suppression window)")
            return None
        
        confidence = smoothed_error / self.threshold
        
        normalized_metrics = self.normalize(feature_vector)[0]
        reconstructed, _ = self.predict(feature_vector)
        reconstructed_denorm = self.denormalize(reconstructed)[0]
        
        affected_metrics = self._identify_affected_metrics(
            feature_vector[0], reconstructed_denorm
        )
        
        anomaly = {
            "agent_id": agent_id,
            "timestamp": metrics.get("timestamp", int(current_time * 1000)),
            "reconstruction_error": smoothed_error,
            "threshold": self.threshold,
            "confidence": confidence,
            "severity": self._compute_severity(confidence),
            "affected_metrics": affected_metrics,
            "message": f"Anomaly detected with {confidence:.2f}x threshold",
        }
        
        self.last_anomaly_time[agent_id] = current_time
        
        logger.warning(
            f"Anomaly detected for agent {agent_id}: "
            f"error={smoothed_error:.6f}, threshold={self.threshold:.6f}, "
            f"confidence={confidence:.2f}x, severity={anomaly['severity']}"
        )
        
        return anomaly

    def _compute_severity(self, confidence: float) -> str:
        if confidence > 5.0:
            return "critical"
        elif confidence > 2.0:
            return "warning"
        else:
            return "info"

    def _identify_affected_metrics(
        self, original: np.ndarray, reconstructed: np.ndarray
    ) -> List[str]:
        errors = np.abs(original - reconstructed)
        metric_names = ["cpu", "ram", "network", "disk"]
        
        affected = []
        for i, name in enumerate(metric_names):
            if i < len(errors) and errors[i] > 0.2:
                affected.append(name)
        
        return affected if affected else ["unknown"]

    def reset_agent(self, agent_id: str) -> None:
        if agent_id in self.error_windows:
            del self.error_windows[agent_id]
        if agent_id in self.last_anomaly_time:
            del self.last_anomaly_time[agent_id]
        logger.info(f"Reset detector state for agent {agent_id}")

    def get_agent_stats(self, agent_id: str) -> Dict:
        return {
            "error_window": list(self.error_windows.get(agent_id, [])),
            "last_anomaly_time": self.last_anomaly_time.get(agent_id),
            "threshold": self.threshold,
        }

    def update_threshold(self, threshold_multiplier: float) -> None:
        self.threshold_multiplier = threshold_multiplier
        self.threshold = self._compute_threshold()
        logger.info(f"Threshold updated to {self.threshold:.6f}")
