"""Verify worker — handles QA Engineer, DevOps, Release Manager."""

from __future__ import annotations

import asyncio
import logging

from shared.models import QueueName
from shared.worker import BaseWorker

from .agents import AGENT_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


async def main() -> None:
    worker = BaseWorker(
        queue_name=QueueName.VERIFY,
        agent_registry=AGENT_REGISTRY,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
