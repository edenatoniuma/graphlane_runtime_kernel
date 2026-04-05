from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import redis.asyncio as async_redis
from psycopg_pool import AsyncConnectionPool


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from graphlane import AppSpec, ModelSpec, TurnRequest
from graphlane.adapters.postgres import PostgresOutboxStore, PostgresRevisionStore
from graphlane.adapters.redis import RedisEventBus, RedisLimiter, RedisLockManager
from graphlane.api import KernelBuilder


async def main() -> None:
    database_url = os.environ["GRAPHLANE_DATABASE_URL"]
    redis_url = os.environ["GRAPHLANE_REDIS_URL"]

    pool = AsyncConnectionPool(conninfo=database_url, open=False)
    await pool.open()
    redis_client = async_redis.from_url(redis_url, decode_responses=True)

    try:
        revision_store = PostgresRevisionStore(pool)
        await revision_store.ensure_tables()

        outbox_store = PostgresOutboxStore(pool)
        await outbox_store.ensure_tables()

        event_bus = RedisEventBus(redis_client)
        lock_manager = RedisLockManager(redis_client)
        limiter = RedisLimiter(redis_client, limit=100)

        kernel = (
            KernelBuilder()
            .with_revision_store(revision_store)
            .with_event_bus(event_bus)
            .with_lock_manager(lock_manager)
            .with_limiter(limiter)
            .build()
        )

        await kernel.publish_revision(
            AppSpec(
                app_id="demo",
                name="demo",
                revision=1,
                app_type="REACT",
                enabled_patterns=["REACT"],
                prompt="echo",
                model=ModelSpec(provider="mock", model="demo-model"),
            )
        )

        result = await kernel.invoke(
            TurnRequest(
                app_id="demo",
                session_id="demo-session",
                query="hello-from-real-adapters",
            )
        )

        print("assistant_content:", result.assistant_content)
        print("outbox_table_ready:", type(outbox_store).__name__)
    finally:
        await redis_client.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

