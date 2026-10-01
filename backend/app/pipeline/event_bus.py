"""
A tiny message bus that sits between pipeline stages.

Each stage reads from one topic and writes to the next topic, so stages
never call each other directly. That's the important part, not the
implementation: as far as every stage is concerned, it just has a queue to
read from and a queue to write to.

Right now InProcessEventBus backs each topic with an asyncio.Queue, which
is enough for one process. If this ever needed to run across multiple
machines, you would write a KafkaEventBus (or one for Kinesis/Pub/Sub) that
implements the same publish/subscribe methods, and nothing in ingest.py,
normalize.py, entity_link.py, enrich.py or publish.py would need to change -
they only know about EventBus, not about asyncio.Queue.
"""
from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class EventBus(Generic[T]):
    async def publish(self, topic: str, item: T) -> None:
        raise NotImplementedError

    def queue_depth(self, topic: str) -> int:
        raise NotImplementedError

    async def get(self, topic: str) -> T:
        raise NotImplementedError


class InProcessEventBus(EventBus):
    """asyncio.Queue-backed implementation, good enough for a single process.

    maxsize is intentionally finite: a bounded queue is what makes
    "backpressure" a real, measurable thing (queue_depth climbing toward
    maxsize means downstream can't keep up) instead of just a word in a
    design doc.
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._queues: dict[str, asyncio.Queue] = {}

    def _queue_for(self, topic: str) -> asyncio.Queue:
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue(maxsize=self._maxsize)
        return self._queues[topic]

    async def publish(self, topic: str, item) -> None:
        await self._queue_for(topic).put(item)

    async def get(self, topic: str):
        return await self._queue_for(topic).get()

    def queue_depth(self, topic: str) -> int:
        return self._queue_for(topic).qsize()
