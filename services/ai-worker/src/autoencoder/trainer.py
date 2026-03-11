import json
import logging
import pickle
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader, TensorDataset

from .model import Autoencoder, MetricAutoencoder

logger = logging.getLogger(__name__)


class Trainer:
    def __init__(
        self,
        model: Optional[Autoencoder] = None,
        learning_rate: float = 0.001,
        batch_size: int = 64,
        patience: int = 10,
        device: Optional[str] = None,
    ):
        self.model = model or MetricAutoencoder()
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.patience = patience
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model.to(self.device)
        
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        self.scheduler = ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5, verbose=True
        )
        
        self.scaler = MinMaxScaler()
        self.train_losses: List[float] = []
        self.val_losses: List[float] = []
        self.best_val_loss = float("inf")
        self.baseline_errors: Optional[np.ndarray] = None

    async def load_data_from_influx(
        self, influx_client, agent_id: str, hours: int = 168
    ) -> np.ndarray:
        logger.info(f"Loading {hours} hours of data for agent {agent_id}")
        
        raw_data = await influx_client.query_training_data(agent_id, hours=hours)
        
        if not raw_data:
            raise ValueError(f"No data found for agent {agent_id}")
        
        features = []
        for row in raw_data:
            features.append([
                row.get("cpu", 0.0),
                row.get("ram", 0.0),
                row.get("network_in", 0.0) + row.get("network_out", 0.0),
                row.get("disk_read", 0.0) + row.get("disk_write", 0.0),
            ])
        
        return np.array(features, dtype=np.float32)

    def normalize(
        self, data: np.ndarray, fit: bool = True
    ) -> np.ndarray:
        if fit:
            normalized = self.scaler.fit_transform(data)
        else:
            normalized = self.scaler.transform(data)
        return normalized

    def denormalize(self, data: np.ndarray) -> np.ndarray:
        return self.scaler.inverse_transform(data)

    def split_data(
        self, data: np.ndarray, val_ratio: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray]:
        return train_test_split(data, test_size=val_ratio, shuffle=True, random_state=42)

    def create_dataloader(
        self, data: np.ndarray, shuffle: bool = True
    ) -> DataLoader:
        tensor = torch.tensor(data, dtype=torch.float32)
        dataset = TensorDataset(tensor)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=shuffle)

    def train_epoch(self, train_loader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        
        for (batch,) in train_loader:
            batch = batch.to(self.device)
            
            self.optimizer.zero_grad()
            reconstructed = self.model(batch)
            loss = self.model.compute_loss(batch, reconstructed)
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
        
        return total_loss / len(train_loader)

    def validate(self, val_loader: DataLoader) -> float:
        self.model.eval()
        total_loss = 0.0
        
        with torch.no_grad():
            for (batch,) in val_loader:
                batch = batch.to(self.device)
                reconstructed = self.model(batch)
                loss = self.model.compute_loss(batch, reconstructed)
                total_loss += loss.item()
        
        return total_loss / len(val_loader)

    def train(
        self,
        train_data: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        epochs: int = 100,
        checkpoint_dir: str = "/models",
        checkpoint_interval: int = 10,
    ) -> Dict:
        checkpoint_path = Path(checkpoint_dir)
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        
        train_normalized = self.normalize(train_data, fit=True)
        
        if val_data is None:
            train_normalized, val_normalized = self.split_data(train_normalized)
        else:
            val_normalized = self.normalize(val_data, fit=False)
        
        train_loader = self.create_dataloader(train_normalized, shuffle=True)
        val_loader = self.create_dataloader(val_normalized, shuffle=False)
        
        self.train_losses = []
        self.val_losses = []
        best_epoch = 0
        patience_counter = 0
        self.best_val_loss = float("inf")
        
        logger.info(f"Starting training for {epochs} epochs on {self.device}")
        logger.info(f"Training samples: {len(train_normalized)}, Validation samples: {len(val_normalized)}")
        
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            val_loss = self.validate(val_loader)
            
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            
            self.scheduler.step(val_loss)
            
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                best_epoch = epoch
                patience_counter = 0
                self._save_checkpoint(checkpoint_path / "best_model.pt")
                logger.info(f"Epoch {epoch+1}: New best model saved (val_loss={val_loss:.6f})")
            else:
                patience_counter += 1
            
            if (epoch + 1) % checkpoint_interval == 0:
                self._save_checkpoint(checkpoint_path / f"checkpoint_epoch_{epoch+1}.pt")
            
            if (epoch + 1) % 5 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}, "
                    f"Best Val Loss: {self.best_val_loss:.6f} (epoch {best_epoch+1})"
                )
            
            if patience_counter >= self.patience:
                logger.info(f"Early stopping at epoch {epoch+1} (patience={self.patience})")
                break
        
        self._compute_baseline_errors(val_normalized)
        
        self._save_scaler(checkpoint_path / "scaler.pkl")
        self._save_baseline_errors(checkpoint_path / "baseline.npy")
        self._save_training_history(checkpoint_path / "training_history.json")
        
        return {
            "best_epoch": best_epoch + 1,
            "best_val_loss": self.best_val_loss,
            "final_train_loss": self.train_losses[-1],
            "final_val_loss": self.val_losses[-1],
            "total_epochs": len(self.train_losses),
        }

    def _compute_baseline_errors(self, data: np.ndarray) -> None:
        tensor = torch.tensor(data, dtype=torch.float32).to(self.device)
        self.model.eval()
        with torch.no_grad():
            errors = self.model.reconstruction_error(tensor).cpu().numpy()
        self.baseline_errors = errors

    def _save_checkpoint(self, path: Path) -> None:
        self.model.save_model(str(path))

    def _save_scaler(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self.scaler, f)

    def _save_baseline_errors(self, path: Path) -> None:
        np.save(str(path), self.baseline_errors)

    def _save_training_history(self, path: Path) -> None:
        history = {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
            "best_val_loss": self.best_val_loss,
        }
        with open(path, "w") as f:
            json.dump(history, f, indent=2)

    def load_checkpoint(self, checkpoint_path: str) -> None:
        self.model = Autoencoder.load_model(checkpoint_path, device=self.device)
        self.model.to(self.device)
        
        base_path = Path(checkpoint_path).parent
        scaler_path = base_path / "scaler.pkl"
        baseline_path = base_path / "baseline.npy"
        
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
        
        if baseline_path.exists():
            self.baseline_errors = np.load(str(baseline_path))

    def continue_training(
        self,
        train_data: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        epochs: int = 50,
        checkpoint_dir: str = "/models",
    ) -> Dict:
        logger.info("Continuing training from existing model")
        
        history_path = Path(checkpoint_dir) / "training_history.json"
        if history_path.exists():
            with open(history_path, "r") as f:
                history = json.load(f)
            self.train_losses = history.get("train_losses", [])
            self.val_losses = history.get("val_losses", [])
            self.best_val_loss = history.get("best_val_loss", float("inf"))
        
        return self.train(train_data, val_data, epochs, checkpoint_dir)

    def get_training_metrics(self) -> Dict:
        return {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
            "best_val_loss": self.best_val_loss,
            "total_epochs": len(self.train_losses),
            "device": self.device,
        }
