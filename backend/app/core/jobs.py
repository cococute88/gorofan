"""Background job queue abstraction (design 8.8).

MVP: InProcessJobQueue (asyncio tasks). Swap to Celery/ARQ via the same Protocol
with zero core changes (design 8.17 / FUT-3). Idempotency keys prevent duplicate
execution; transient errors retry with exponential backoff.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.core.logging import get_logger

log = get_logger("jobs")

JobHandler = Callable[[dict], Awaitable[None]]


@dataclass
class Job:
    kind: str
    payload: dict
    idempotency_key: str
    max_retries: int = 3


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> None: ...
    def register(self, kind: str, handler: JobHandler) -> None: ...
    async def drain(self) -> None: ...


@dataclass
class InProcessJobQueue:
    """asyncio-task based queue for single-process MVP."""

    _handlers: dict[str, JobHandler] = field(default_factory=dict)
    _seen_keys: set[str] = field(default_factory=set)
    _tasks: set[asyncio.Task] = field(default_factory=set)

    def register(self, kind: str, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    async def enqueue(self, job: Job) -> None:
        if job.idempotency_key in self._seen_keys:
            log.info("job.skip.idempotent")
            return
        self._seen_keys.add(job.idempotency_key)
        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job: Job) -> None:
        handler = self._handlers.get(job.kind)
        if handler is None:
            log.warning("job.no_handler")
            return
        attempt = 0
        while True:
            try:
                await handler(job.payload)
                log.info("job.done")
                return
            except Exception:  # noqa: BLE001
                attempt += 1
                if attempt > job.max_retries:
                    log.exception("job.failed")
                    # failure must not break user flow (BR-6)
                    return
                await asyncio.sleep(min(2**attempt, 30))

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


def build_job_queue(backend: str) -> JobQueue:
    # Extension point: 'celery'/'arq' would return alternate implementations (FUT-3).
    return InProcessJobQueue()
