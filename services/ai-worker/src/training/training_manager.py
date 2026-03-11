import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from ..autoencoder.trainer import Trainer
from ..config.settings import settings
from ..storage.influx_writer import InfluxWriter
from ..storage.postgres import PostgresClient

logger = logging.getLogger(__name__)


class TrainingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingTask:
    task_id: str
    status: TrainingStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    agent_id: Optional[str] = None
    error: Optional[str] = None
    metrics: Optional[Dict] = None


class TrainingManager:
    def __init__(
        self,
        influx_client: InfluxWriter,
        postgres_client: PostgresClient,
        model_path: str = None,
    ):
        self.influx_client = influx_client
        self.postgres_client = postgres_client
        self.model_path = model_path or settings.model_path
        self.tasks: Dict[str, TrainingTask] = {}
        self._lock = asyncio.Lock()

    async def start_training(
        self,
        agent_id: Optional[str] = None,
        hours: int = 168,
    ) -> str:
        task_id = str(uuid.uuid4())
        
        async with self._lock:
            task = TrainingTask(
                task_id=task_id,
                status=TrainingStatus.PENDING,
                started_at=datetime.now(timezone.utc),
                agent_id=agent_id,
            )
            self.tasks[task_id] = task
        
        asyncio.create_task(self._run_training(task_id, agent_id, hours))
        
        logger.info(f"Training task {task_id} started for agent={agent_id}")
        return task_id

    async def _run_training(
        self,
        task_id: str,
        agent_id: Optional[str],
        hours: int,
    ) -> None:
        async with self._lock:
            self.tasks[task_id].status = TrainingStatus.RUNNING
        
        try:
            trainer = Trainer()
            
            data = await trainer.load_data_from_influx(
                self.influx_client,
                agent_id=agent_id or "all",
                hours=hours,
            )
            
            if len(data) < 100:
                raise ValueError(f"Insufficient training data: {len(data)} samples")
            
            metrics = trainer.train(
                train_data=data,
                epochs=100,
                checkpoint_dir=self.model_path.rsplit(".", 1)[0],
            )
            
            async with self._lock:
                self.tasks[task_id].status = TrainingStatus.COMPLETED
                self.tasks[task_id].completed_at = datetime.now(timezone.utc)
                self.tasks[task_id].metrics = metrics
            
            logger.info(f"Training task {task_id} completed: {metrics}")
            
        except Exception as e:
            logger.error(f"Training task {task_id} failed: {e}")
            async with self._lock:
                self.tasks[task_id].status = TrainingStatus.FAILED
                self.tasks[task_id].completed_at = datetime.now(timezone.utc)
                self.tasks[task_id].error = str(e)

    async def get_task(self, task_id: str) -> Optional[TrainingTask]:
        async with self._lock:
            return self.tasks.get(task_id)

    async def list_tasks(self) -> Dict[str, Dict]:
        async with self._lock:
            return {
                task_id: {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "agent_id": task.agent_id,
                    "error": task.error,
                    "metrics": task.metrics,
                }
                for task_id, task in self.tasks.items()
            }

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = TrainingStatus.FAILED
                self.tasks[task_id].error = "Cancelled by user"
                self.tasks[task_id].completed_at = datetime.now(timezone.utc)
                return True
            return False
