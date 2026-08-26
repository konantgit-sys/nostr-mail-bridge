"""SQLite: подключение с WAL и индексами (вертикальная оптимизация).

WAL: конкурентные чтения не блокируют запись моста; synchronous=NORMAL
для скорости при сохранении целостности. Индексы на горячие поля.
"""
from __future__ import annotations

import sqlite3

# один коннектор на поток (мост и веб-запросы — разные потоки)
_local = threading_local = None  # заглушка для старых интерпретаторов


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")
    _ensure_indexes(conn)
    return conn


def _ensure_indexes(conn: sqlite3.Connection):
    """Индексы создаются один раз (IF NOT EXISTS) — дешёво на каждый коннект."""
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inbox_received ON inbox(received_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inbox_read ON inbox(is_read)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_sent ON outbox(sent_at DESC)")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # таблиц ещё нет (первый запуск до миграции моста)


def query(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    """Короткий хелпер для чтения: коннект → запрос → закрыть."""
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(db_path: str, sql: str, params: tuple = ()) -> int:
    """Короткий хелпер для записи: возвращает rowcount."""
    with connect(db_path) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount
