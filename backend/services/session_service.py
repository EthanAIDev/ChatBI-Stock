import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from backend.config import settings

STOCK_MAP = {
    '贵州茅台': '600519.SH',
    '五粮液': '000858.SZ',
    '中芯国际': '688981.SH',
    '广发证券': '000776.SZ',
}
ACTION_KEYWORDS = ['比较', '走势', '最高收盘价', '最低收盘价', '平均收盘价', '收盘价', '涨跌幅', '成交额']
STOP_WORDS = ['查询', '一下', '一下子', '帮我', '请', '看看', '一下吧', '一下呢']


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _now_ts() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = {row['name'] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _extract_title(first_message: str) -> str:
    text = re.sub(r'\s+', '', first_message)
    for stop_word in STOP_WORDS:
        text = text.replace(stop_word, '')
    stock_hits = [name for name in STOCK_MAP if name in text]
    action_hit = next((keyword for keyword in ACTION_KEYWORDS if keyword in text), '')
    date_hit = ''
    date_match = re.search(r'(\d{4})[-年](\d{1,2})(?:[-月](\d{1,2}))?', text)
    if date_match:
        year, month, day = date_match.group(1), date_match.group(2), date_match.group(3)
        date_hit = f'{year}{int(month):02d}'
        if day:
            date_hit += f'{int(day):02d}'
    if action_hit == '比较' and stock_hits:
        title = f'比较{"".join(stock_hits[:2])}'
    elif stock_hits and action_hit:
        title = f'{stock_hits[0]}{action_hit}'
    elif stock_hits and date_hit:
        title = f'{stock_hits[0]}{date_hit}'
    elif action_hit and date_hit:
        title = f'{action_hit}{date_hit}'
    elif stock_hits:
        title = stock_hits[0]
    elif action_hit:
        title = action_hit
    else:
        title = text[:20]
    return title[:20] or '新对话'


def ensure_app_tables() -> None:
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
            ON chat_sessions(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sql_text TEXT,
                result_preview TEXT,
                chart_path TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
            ON chat_messages(session_id, created_at ASC, id ASC);
            """
        )
        _ensure_column(conn, 'chat_sessions', 'is_pinned', 'INTEGER NOT NULL DEFAULT 0')


def create_session(user_id: str, title: str = '新对话') -> str:
    session_id = f'session_{uuid.uuid4().hex}'
    timestamp = _now_ts()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at, is_pinned)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (session_id, user_id, title, timestamp, timestamp),
        )
    return session_id


def list_sessions(user_id: str) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT session_id, user_id, title, created_at, updated_at, is_pinned
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY is_pinned DESC, updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            'session_id': row['session_id'],
            'user_id': row['user_id'],
            'title': row['title'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'is_pinned': bool(row['is_pinned']),
        }
        for row in rows
    ]


def get_session(session_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT session_id, user_id, title, created_at, updated_at, is_pinned
            FROM chat_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return {
        'session_id': row['session_id'],
        'user_id': row['user_id'],
        'title': row['title'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'is_pinned': bool(row['is_pinned']),
    }


def user_can_access_session(session_id: str, user_id: str, is_admin: bool = False) -> bool:
    session = get_session(session_id)
    if not session:
        return False
    return is_admin or session['user_id'] == user_id


def get_messages(session_id: str) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, sql_text, result_preview, chart_path, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    return [
        {
            'id': row['id'],
            'role': row['role'],
            'content': row['content'],
            'sql_text': row['sql_text'],
            'result_preview': row['result_preview'],
            'chart_path': row['chart_path'],
            'created_at': row['created_at'],
        }
        for row in rows
    ]


def add_message(
    session_id: str,
    role: str,
    content: str,
    sql_text: str | None = None,
    result_preview: str | None = None,
    chart_path: str | None = None,
) -> None:
    timestamp = _now_ts()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, sql_text, result_preview, chart_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, sql_text, result_preview, chart_path, timestamp),
        )
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (timestamp, session_id))


def update_title_if_placeholder(session_id: str, first_message: str) -> None:
    with _get_conn() as conn:
        row = conn.execute("SELECT title FROM chat_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row and row['title'] == '新对话':
            conn.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (_extract_title(first_message), _now_ts(), session_id),
            )


def rename_session(session_id: str, new_title: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (new_title.strip()[:50], _now_ts(), session_id),
        )
        return cursor.rowcount > 0


def rename_session_for_user(session_id: str, user_id: str, new_title: str, is_admin: bool = False) -> bool:
    if not user_can_access_session(session_id, user_id, is_admin):
        return False
    return rename_session(session_id, new_title)


def set_session_pinned(session_id: str, is_pinned: bool) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            "UPDATE chat_sessions SET is_pinned = ?, updated_at = ? WHERE session_id = ?",
            (1 if is_pinned else 0, _now_ts(), session_id),
        )
        return cursor.rowcount > 0


def set_session_pinned_for_user(session_id: str, user_id: str, is_pinned: bool, is_admin: bool = False) -> bool:
    if not user_can_access_session(session_id, user_id, is_admin):
        return False
    return set_session_pinned(session_id, is_pinned)


def delete_session(session_id: str) -> bool:
    with _get_conn() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM query_audit WHERE session_id = ?", (session_id,))
        history_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'chat_messages_langchain'"
        ).fetchone()
        if history_table:
            conn.execute("DELETE FROM chat_messages_langchain WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        return cursor.rowcount > 0


def delete_session_for_user(session_id: str, user_id: str, is_admin: bool = False) -> bool:
    if not user_can_access_session(session_id, user_id, is_admin):
        return False
    return delete_session(session_id)


def extract_context(messages: list[dict[str, Any]], max_rounds: int = 5) -> str:
    rounds = []
    for msg in messages:
        if msg['role'] == 'user':
            rounds.append({'question': msg['content'], 'sql': ''})
        elif msg['role'] == 'assistant' and rounds:
            rounds[-1]['sql'] = msg.get('sql_text', '')
    recent = rounds[-max_rounds:] if len(rounds) > max_rounds else rounds
    lines = []
    for index, item in enumerate(recent):
        lines.append(f"[第{index + 1}轮] 用户问: {item['question']}")
        if item['sql']:
            lines.append(f"[第{index + 1}轮] 执行SQL: {item['sql']}")
    return '\n'.join(lines)
