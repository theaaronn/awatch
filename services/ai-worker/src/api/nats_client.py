import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional

import nats
from nats.js.api import ConsumerConfig, AckPolicy
from nats.aio.msg import Msg

logger = logging.getLogger(__name__)


class NATSConsumer:
    def __init__(self, nats_url: str, subject: str, durable_name: str):
        self.nats_url = nats_url
        self.subject = subject
        self.durable_name = durable_name
        self.nc = None
        self.js = None
        self.sub = None
        self.is_running = False
        self.dlq_subject = "metrics.dlq"
        self._messages_processed = 0
        self._start_time = None

    async def connect(self) -> None:
        self.nc = await nats.connect(
            self.nats_url,
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
        )
        self.js = self.nc.jetstream()
        logger.info(f"Connected to NATS at {self.nats_url}")

    async def setup_stream(self) -> None:
        streams = await self.js.streams_info()
        stream_names = [s.config.name for s in streams]

        if "METRICS" not in stream_names:
            try:
                await self.js.add_stream(
                    name="METRICS",
                    subjects=["metrics.>", "agents.>"],
                    retention="limits",
                    max_age=86400,  # 24 hours
                )
                logger.info("Created METRICS stream")
            except Exception as e:
                logger.warning(f"Could not create METRICS stream (may already exist with different name): {e}")
        else:
            logger.info("METRICS stream already exists, skipping")

        if "DLQ" not in stream_names:
            try:
                await self.js.add_stream(
                    name="DLQ",
                    subjects=["metrics.dlq"],
                    retention="limits",
                    max_age=604800,  # 7 days
                )
                logger.info("Created DLQ stream")
            except Exception as e:
                logger.warning(f"Could not create DLQ stream: {e}")
        else:
            logger.info("DLQ stream already exists, skipping")

    async def create_subscription(self) -> None:
        self.sub = await self.js.pull_subscribe(
            self.subject,
            durable=self.durable_name,
            config=ConsumerConfig(
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=3,
                ack_wait=30,
            ),
        )
        logger.info(f"Created pull subscription on {self.subject}")

    async def consume_batch(self, batch_size: int = 100) -> List[Dict]:
        try:
            msgs = await self.sub.fetch(batch_size, timeout=5.0)
            results = []
            for msg in msgs:
                try:
                    data = json.loads(msg.data.decode())
                    data["_msg"] = msg  # Store original message for ACK
                    results.append(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    await msg.ack()
            return results
        except nats.errors.TimeoutError:
            return []

    async def process_messages(self, callback: Callable) -> None:
        self.is_running = True
        self._start_time = asyncio.get_event_loop().time()
        logger.info("Starting message processing loop")

        while self.is_running:
            try:
                messages = await self.consume_batch(batch_size=100)
                
                if not messages:
                    await asyncio.sleep(1.0)
                    continue

                for msg_data in messages:
                    msg = msg_data.pop("_msg", None)
                    if not msg:
                        continue

                    try:
                        await callback(msg_data)
                        await msg.ack()
                        self._messages_processed += 1

                        if self._messages_processed % 100 == 0:
                            elapsed = asyncio.get_event_loop().time() - self._start_time
                            rate = self._messages_processed / elapsed if elapsed > 0 else 0
                            logger.info(f"Processed {self._messages_processed} messages ({rate:.2f} msg/sec)")

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

                        try:
                            metadata = msg.metadata
                            if metadata and metadata.num_delivered >= 3:
                                await self.js.publish(self.dlq_subject, msg.data)
                                logger.warning(f"Message sent to DLQ after 3 failures")
                                await msg.ack()
                            else:
                                await msg.nak()
                        except Exception as nak_err:
                            logger.error(f"Error handling failed message: {nak_err}")
                            await msg.ack()

            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1.0)

        logger.info("Message processing loop stopped")

    async def stop(self) -> None:
        self.is_running = False
        logger.info("Stopping NATS consumer")

    async def close(self) -> None:
        self.is_running = False
        
        if self.sub:
            try:
                await self.sub.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

        if self.nc:
            try:
                await self.nc.drain()
                await self.nc.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        logger.info("NATS connection closed")

    async def get_pending_count(self) -> int:
        if not self.js or not self.sub:
            return 0
        try:
            info = await self.js.consumer_info("METRICS", self.durable_name)
            return info.num_pending
        except Exception as e:
            logger.error(f"Failed to get pending count: {e}")
            return 0

    def get_stats(self) -> Dict:
        elapsed = 0
        if self._start_time:
            elapsed = asyncio.get_event_loop().time() - self._start_time
        rate = self._messages_processed / elapsed if elapsed > 0 else 0
        return {
            "messages_processed": self._messages_processed,
            "elapsed_seconds": elapsed,
            "messages_per_second": rate,
            "is_running": self.is_running,
        }
