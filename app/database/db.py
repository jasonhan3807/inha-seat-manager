"""SQLite 저장소. 표준 라이브러리 sqlite3만 사용한다.

개인정보(학번, 비밀번호, 쿠키 등)는 저장하지 않는다.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS watch_seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    seat_id TEXT NOT NULL,
    seat_label TEXT NOT NULL,
    last_status TEXT,
    last_notified_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(room_id, seat_id)
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- seat_available | system
    room_id TEXT,
    room_name TEXT,
    seat_id TEXT,
    seat_label TEXT,
    status TEXT,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- query | query_error | monitor | assign | watch
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

HISTORY_LIMIT = 5000  # 기록이 무한히 쌓이지 않도록 오래된 항목 정리


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def ping(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # ---- 희망 좌석 ----
    def add_watch(self, room_id: str, seat_id: str, seat_label: str) -> dict[str, Any] | None:
        try:
            cur = self._exec(
                "INSERT INTO watch_seats(room_id, seat_id, seat_label, created_at) VALUES (?,?,?,?)",
                (room_id, seat_id, seat_label, now_iso()),
            )
        except sqlite3.IntegrityError:
            return None
        return self.get_watch(cur.lastrowid)

    def get_watch(self, watch_id: int) -> dict[str, Any] | None:
        rows = self._all("SELECT * FROM watch_seats WHERE id=?", (watch_id,))
        return rows[0] if rows else None

    def list_watches(self) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM watch_seats ORDER BY room_id, id")

    def remove_watch(self, watch_id: int) -> bool:
        return self._exec("DELETE FROM watch_seats WHERE id=?", (watch_id,)).rowcount > 0

    def update_watch_state(self, watch_id: int, status: str, notified: bool) -> None:
        if notified:
            self._exec(
                "UPDATE watch_seats SET last_status=?, last_notified_at=? WHERE id=?",
                (status, now_iso(), watch_id),
            )
        else:
            self._exec("UPDATE watch_seats SET last_status=? WHERE id=?", (status, watch_id))

    # ---- 알림 ----
    def add_notification(self, kind: str, message: str, **fields: Any) -> dict[str, Any]:
        cur = self._exec(
            "INSERT INTO notifications(kind, room_id, room_name, seat_id, seat_label, status, message, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                kind,
                fields.get("room_id"),
                fields.get("room_name"),
                fields.get("seat_id"),
                fields.get("seat_label"),
                fields.get("status"),
                message,
                now_iso(),
            ),
        )
        return self._all("SELECT * FROM notifications WHERE id=?", (cur.lastrowid,))[0]

    def list_notifications(self, limit: int = 100, after_id: int = 0) -> list[dict[str, Any]]:
        return self._all(
            "SELECT * FROM notifications WHERE id>? ORDER BY id DESC LIMIT ?", (after_id, limit)
        )

    def unread_count(self) -> int:
        return self._all("SELECT COUNT(*) AS c FROM notifications WHERE is_read=0")[0]["c"]

    def mark_all_read(self) -> None:
        self._exec("UPDATE notifications SET is_read=1 WHERE is_read=0")

    # ---- 이력 ----
    def log(self, kind: str, detail: str) -> None:
        self._exec("INSERT INTO history(kind, detail, created_at) VALUES (?,?,?)", (kind, detail, now_iso()))
        self._exec(
            "DELETE FROM history WHERE id <= (SELECT MAX(id) FROM history) - ?", (HISTORY_LIMIT,)
        )

    def list_history(self, limit: int = 200, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            return self._all("SELECT * FROM history WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit))
        return self._all("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))

    # ---- 설정 ----
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        rows = self._all("SELECT value FROM settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self._exec(
            "INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
