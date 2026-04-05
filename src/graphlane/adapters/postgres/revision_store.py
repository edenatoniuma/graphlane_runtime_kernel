from __future__ import annotations

import json
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from graphlane.api.specs import AppSpec
from graphlane.revision.models import ActiveRevision, RevisionSnapshot


class PostgresRevisionStore:
    def __init__(
        self,
        pool: AsyncConnectionPool,
        *,
        revisions_table: str = "graphlane_revisions",
        active_table: str = "graphlane_active_revisions",
    ) -> None:
        self._pool = pool
        self._revisions_table = revisions_table
        self._active_table = active_table

    async def ensure_tables(self) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._revisions_table} (
                        app_id TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        spec_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        PRIMARY KEY (app_id, revision)
                    )
                    """
                )
                await cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._active_table} (
                        app_id TEXT PRIMARY KEY,
                        revision INTEGER NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            await conn.commit()

    async def save_snapshot(self, snapshot: RevisionSnapshot) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO {self._revisions_table} (app_id, revision, spec_json, created_at)
                    VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT (app_id, revision)
                    DO UPDATE SET spec_json = EXCLUDED.spec_json, created_at = EXCLUDED.created_at
                    """,
                    (
                        snapshot.app_id,
                        snapshot.revision,
                        json.dumps(snapshot.spec.to_dict(), ensure_ascii=False),
                        snapshot.created_at,
                    ),
                )
            await conn.commit()

    async def get_snapshot(self, app_id: str, revision: int) -> RevisionSnapshot | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"""
                    SELECT app_id, revision, spec_json, created_at
                    FROM {self._revisions_table}
                    WHERE app_id = %s AND revision = %s
                    """,
                    (app_id, revision),
                )
                row = await cur.fetchone()
        if row is None:
            return None
        spec_json = row["spec_json"]
        if isinstance(spec_json, str):
            spec_data = json.loads(spec_json)
        else:
            spec_data = dict(spec_json)
        return RevisionSnapshot(
            app_id=str(row["app_id"]),
            revision=int(row["revision"]),
            spec=AppSpec.from_dict(spec_data),
            created_at=self._as_datetime(row["created_at"]),
        )

    async def set_active_revision(self, app_id: str, revision: int) -> None:
        active = ActiveRevision(app_id=app_id, revision=revision)
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO {self._active_table} (app_id, revision, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (app_id)
                    DO UPDATE SET revision = EXCLUDED.revision, updated_at = EXCLUDED.updated_at
                    """,
                    (active.app_id, active.revision, active.updated_at),
                )
            await conn.commit()

    async def get_active_revision(self, app_id: str) -> ActiveRevision | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"""
                    SELECT app_id, revision, updated_at
                    FROM {self._active_table}
                    WHERE app_id = %s
                    """,
                    (app_id,),
                )
                row = await cur.fetchone()
        if row is None:
            return None
        return ActiveRevision(
            app_id=str(row["app_id"]),
            revision=int(row["revision"]),
            updated_at=self._as_datetime(row["updated_at"]),
        )

    async def clear_active_revision(self, app_id: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM {self._active_table} WHERE app_id = %s",
                    (app_id,),
                )
            await conn.commit()

    @staticmethod
    def _as_datetime(value: datetime) -> datetime:
        return value
