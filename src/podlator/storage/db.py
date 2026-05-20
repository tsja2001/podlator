"""SQLite 任务存储。使用 aiosqlite 异步访问。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite


class TaskStore:
    """SQLite 任务存储，管理任务的 CRUD 操作。

    维护一个持久化连接以支持 :memory: 数据库。
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def _get_conn(self) -> aiosqlite.Connection:
        """获取共享连接（惰性初始化）。"""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            # 启用 WAL 模式提升并发性能（文件数据库）
            await self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    async def initialize(self) -> None:
        """创建表（如不存在）。"""
        db = await self._get_conn()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id              TEXT PRIMARY KEY,
                source_url      TEXT NOT NULL,
                title           TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                current_node    TEXT,
                error_message   TEXT,
                brief_path      TEXT,
                audio_path      TEXT,
                cost_usd        REAL NOT NULL DEFAULT 0.0,
                duration_seconds REAL,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)"
        )
        await db.commit()

    async def create(self, task_id: str, source_url: str) -> dict[str, Any]:
        """创建新任务，返回完整记录。"""
        now = datetime.now(UTC).isoformat()
        db = await self._get_conn()
        await db.execute(
            """INSERT INTO tasks
               (id, source_url, status, cost_usd, created_at, updated_at)
               VALUES (?, ?, 'pending', 0.0, ?, ?)""",
            (task_id, source_url, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def get(self, task_id: str) -> dict[str, Any] | None:
        """按 ID 查询任务，不存在返回 None。"""
        db = await self._get_conn()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询任务列表，支持按 status 过滤和分页。"""
        db = await self._get_conn()
        if status:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ?"
                " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """更新任务字段，返回更新后的记录。"""
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())

        db = await self._get_conn()
        await db.execute(
            f"UPDATE tasks SET {set_clause}, updated_at = ? WHERE id = ?",
            values + [now, task_id],
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def delete(self, task_id: str) -> bool:
        """删除任务，返回是否删除成功。"""
        db = await self._get_conn()
        cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
