from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    nats_url: str = "nats://localhost:4222"
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "awatch-token"
    influxdb_org: str = "awatch"
    influxdb_bucket: str = "metrics"
    postgres_url: str = "postgresql+asyncpg://awatch:awatch@localhost:5432/awatch"
    model_path: str = "/models/autoencoder.pth"
    threshold: float = 0.1
    websocket_api_keys: List[str] = ["test-api-key"]
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
