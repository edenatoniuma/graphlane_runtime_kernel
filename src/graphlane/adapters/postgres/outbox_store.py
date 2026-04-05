from __future__ import annotations

import json
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from graphlane.side_effects.tasks import SideEffectTask


class PostgresOutboxStore:
    def __init__(
        self,
        pool: AsyncConnectionPool,
        *,
        table_name: str = "graphlane_side_effect_outbox",
    ) -> None:
        self._pool = pool
        self._table_name = table_name

    async def ensure_tables(self) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        id TEXT PRIMARY KEY,
                        task_type TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        traceparent TEXT NULL,
                        status TEXT NOT NULL,
                        retry_count INTEGER NOT NULL,
                        max_retries INTEGER NOT NULL,
                        next_run_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        claimed_at TIMESTAMPTZ NULL,
                        claimed_by TEXT NULL,
                        last_error TEXT NULL
                    )
                    """
                )
            await conn.commit()

    async def add(self, task: SideEffectTask) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO {self._table_name} (
                        id, task_type, payload, traceparent, status, retry_count,
                        max_retries, next_run_at, created_at, updated_at, claimed_at,
                        claimed_by, last_error
                    ) VALUES (
                        %s, %s, %s::jsonb, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        task.id,
                        task.task_type,
                        json.dumps(task.payload, ensure_ascii=False),
                        task.traceparent,
                        task.status,
                        task.retry_count,
                        task.max_retries,
                        task.next_run_at,
                        task.created_at,
                        task.updated_at,
                        task.claimed_at,
                        task.claimed_by,
                        task.last_error,
                    ),
                )
            await conn.commit()

    async def claim_available(self, worker_id: str, limit: int = 10) -> list[SideEffectTask]:
        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        f"""
                        SELECT *
                        FROM {self._table_name}
                        WHERE status = 'pending' AND next_run_at <= NOW()
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = await cur.fetchall()
                    tasks: list[SideEffectTask] = []
                    for row in rows:
                        task = self._row_to_task(row)
                        task.mark_running(worker_id)
                        await cur.execute(
                            f"""
                            UPDATE {self._table_name}
                            SET status = %s, claimed_by = %s, claimed_at = %s, updated_at = %s
                            WHERE id = %s
                            """,
                            (
                                task.status,
                                task.claimed_by,
                                task.claimed_at,
                                task.updated_at,
                                task.id,
                            ),
                        )
                        tasks.append(task)
                    return tasks

    async def mark_done(self, task: SideEffectTask) -> None:
        task.mark_done()
        await self._update_terminal(task)

    async def mark_retry(self, task: SideEffectTask, error_message: str, delay_seconds: float) -> None:
        task.mark_retry(error_message=error_message, delay_seconds=delay_seconds)
        await self._update_terminal(task)

    async def mark_dead(self, task: SideEffectTask, error_message: str) -> None:
        task.mark_dead(error_message=error_message)
        await self._update_terminal(task)

    async def _update_terminal(self, task: SideEffectTask) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    UPDATE {self._table_name}
                    SET status = %s,
                        retry_count = %s,
                        next_run_at = %s,
                        updated_at = %s,
                        claimed_at = %s,
                        claimed_by = %s,
                        last_error = %s
                    WHERE id = %s
                    """,
                    (
                        task.status,
                        task.retry_count,
                        task.next_run_at,
                        task.updated_at,
                        task.claimed_at,
                        task.claimed_by,
                        task.last_error,
                        task.id,
                    ),
                )
            await conn.commit()

    def _row_to_task(self, row: dict) -> SideEffectTask:
        payload = row["payload"]
        if isinstance(payload, str):
            payload_dict = json.loads(payload)
        else:
            payload_dict = dict(payload)
        return SideEffectTask(
            id=str(row["id"]),
            task_type=str(row["task_type"]),
            payload=payload_dict,
            traceparent=row["traceparent"],
            status=str(row["status"]),
            retry_count=int(row["retry_count"]),
            max_retries=int(row["max_retries"]),
            next_run_at=self._as_datetime(row["next_run_at"]),
            created_at=self._as_datetime(row["created_at"]),
            updated_at=self._as_datetime(row["updated_at"]),
            claimed_at=None if row["claimed_at"] is None else self._as_datetime(row["claimed_at"]),
            claimed_by=row["claimed_by"],
            last_error=row["last_error"],
        )

    @staticmethod
    def _as_datetime(value: datetime) -> datetime:
        return value

