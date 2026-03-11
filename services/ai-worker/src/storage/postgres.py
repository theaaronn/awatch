import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base, Incident, Server, AlertConfig

logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(self, database_url: str):
        self._engine = create_async_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def upsert_server(
        self,
        agent_id: str,
        hostname: str,
        ip_address: str,
        agent_version: Optional[str] = None,
    ) -> Server:
        async with self.session() as session:
            result = await session.execute(
                select(Server).where(Server.agent_id == agent_id)
            )
            server = result.scalar_one_or_none()

            if server:
                server.hostname = hostname
                server.ip_address = ip_address
                server.agent_version = agent_version
                server.last_seen = datetime.now(timezone.utc)
                server.status = "online"
            else:
                server = Server(
                    agent_id=agent_id,
                    hostname=hostname,
                    ip_address=ip_address,
                    agent_version=agent_version,
                    status="online",
                    last_seen=datetime.now(timezone.utc),
                )
                session.add(server)

            await session.flush()
            await session.refresh(server)
            return server

    async def mark_server_offline(self, agent_id: str) -> None:
        async with self.session() as session:
            await session.execute(
                update(Server)
                .where(Server.agent_id == agent_id)
                .values(status="offline")
            )

    async def get_servers(self) -> List[Server]:
        async with self.session() as session:
            result = await session.execute(
                select(Server).order_by(Server.created_at.asc())
            )
            return list(result.scalars().all())

    async def get_server_by_agent_id(self, agent_id: str) -> Optional[Server]:
        async with self.session() as session:
            result = await session.execute(
                select(Server).where(Server.agent_id == agent_id)
            )
            return result.scalar_one_or_none()

    async def get_server_by_id(self, server_id: uuid.UUID) -> Optional[Server]:
        async with self.session() as session:
            result = await session.execute(
                select(Server).where(Server.id == server_id)
            )
            return result.scalar_one_or_none()

    async def delete_server(self, agent_id: str) -> bool:
        async with self.session() as session:
            result = await session.execute(
                select(Server).where(Server.agent_id == agent_id)
            )
            server = result.scalar_one_or_none()
            if server:
                await session.delete(server)
                return True
            return False

    async def create_incident(
        self,
        server_id: uuid.UUID,
        severity: str,
        reconstruction_error: float,
        threshold: float,
        confidence: float,
        affected_metrics: List[str],
        message: str,
    ) -> Incident:
        async with self.session() as session:
            incident = Incident(
                server_id=server_id,
                severity=severity,
                status="active",
                reconstruction_error=reconstruction_error,
                threshold=threshold,
                confidence=confidence,
                affected_metrics=",".join(affected_metrics),
                message=message,
            )
            session.add(incident)
            await session.flush()
            await session.refresh(incident)
            return incident

    async def acknowledge_incident(
        self, incident_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Incident]:
        async with self.session() as session:
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident:
                incident.status = "acknowledged"
                incident.acknowledged_by = user_id
                incident.acknowledged_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(incident)
            return incident

    async def resolve_incident(self, incident_id: uuid.UUID) -> Optional[Incident]:
        async with self.session() as session:
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident:
                incident.status = "resolved"
                incident.resolved_at = datetime.now(timezone.utc)
                await session.flush()
                await session.refresh(incident)
            return incident

    async def get_incidents(
        self,
        server_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        async with self.session() as session:
            query = select(Incident)

            if server_id:
                query = query.where(Incident.server_id == server_id)
            if status:
                query = query.where(Incident.status == status)

            query = query.order_by(Incident.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            incidents = list(result.scalars().all())

            for incident in incidents:
                incident.affected_metrics = incident.affected_metrics.split(",")

            return incidents

    async def get_incident_by_id(self, incident_id: uuid.UUID) -> Optional[Incident]:
        async with self.session() as session:
            result = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if incident:
                incident.affected_metrics = incident.affected_metrics.split(",")
            return incident

    async def create_alert_config(
        self,
        server_id: uuid.UUID,
        metric_type: str,
        threshold_multiplier: float = 3.0,
        cooldown_seconds: int = 300,
        is_enabled: bool = True,
    ) -> AlertConfig:
        async with self.session() as session:
            config = AlertConfig(
                server_id=server_id,
                metric_type=metric_type,
                threshold_multiplier=threshold_multiplier,
                cooldown_seconds=cooldown_seconds,
                is_enabled=is_enabled,
            )
            session.add(config)
            await session.flush()
            await session.refresh(config)
            return config

    async def get_alert_configs(
        self, server_id: Optional[uuid.UUID] = None
    ) -> List[AlertConfig]:
        async with self.session() as session:
            query = select(AlertConfig)
            if server_id:
                query = query.where(AlertConfig.server_id == server_id)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_alert_config(
        self,
        config_id: uuid.UUID,
        threshold_multiplier: Optional[float] = None,
        cooldown_seconds: Optional[int] = None,
        is_enabled: Optional[bool] = None,
    ) -> Optional[AlertConfig]:
        async with self.session() as session:
            result = await session.execute(
                select(AlertConfig).where(AlertConfig.id == config_id)
            )
            config = result.scalar_one_or_none()
            if config:
                if threshold_multiplier is not None:
                    config.threshold_multiplier = threshold_multiplier
                if cooldown_seconds is not None:
                    config.cooldown_seconds = cooldown_seconds
                if is_enabled is not None:
                    config.is_enabled = is_enabled
                await session.flush()
                await session.refresh(config)
            return config

    async def delete_alert_config(self, config_id: uuid.UUID) -> bool:
        async with self.session() as session:
            result = await session.execute(
                select(AlertConfig).where(AlertConfig.id == config_id)
            )
            config = result.scalar_one_or_none()
            if config:
                await session.delete(config)
                return True
            return False

    async def close(self) -> None:
        await self._engine.dispose()
        logger.info("PostgreSQL connection closed")
