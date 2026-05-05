import json
import sqlite3
from datetime import datetime
from typing import Any

import bcrypt

from backend.config import settings


MODEL_SETTING_DEFINITIONS = {
    'model_name': {
        'default': settings.model_name,
        'description': '当前使用的模型名称',
    },
    'base_url': {
        'default': settings.dashscope_base_url,
        'description': '模型服务 Base URL',
    },
    'timeout_seconds': {
        'default': settings.query_timeout_seconds,
        'description': '模型请求超时时间（秒）',
    },
    'retry_count': {
        'default': settings.max_retry,
        'description': '模型请求重试次数',
    },
    'max_context_rounds': {
        'default': settings.max_context_rounds,
        'description': '默认上下文轮数',
    },
}

PROMPT_TEMPLATE_DEFINITIONS = {
    'sql_generator_rules': {
        'template_name': 'SQL 生成提示词',
        'description': '用于约束 SQL 生成的系统规则。',
        'content': """规则：
1. 只允许输出 JSON，不要 markdown，不要解释。
2. JSON 格式固定为 {"sql": "..."}
3. 只生成 SELECT 语句，不能生成 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE。
4. 日期字段是 trade_date，格式为 YYYY-MM-DD。
5. 你的唯一职责是生成 SQL。不要用自然语言回答用户的数据问题，文字总结由另一个专门模块完成。
6. 如果涉及走势，优先返回 trade_date 和一个或多个数值列，并按 trade_date 升序。
7. 如果涉及最高/最低收盘价，优先返回 trade_date、close。
8. 如果涉及平均收盘价，使用 AVG(close) 并合理命名列。
9. 如果用户提到股票名称，必须使用 stock_name 过滤。
10. 如果用户说了"总结""分析""归纳""评价"，这只是说明他需要数据——你必须首先生成 SQL 把数据查出来。""",
    },
    'analyst_system_prompt': {
        'template_name': '总结提示词',
        'description': '用于生成分析总结的系统提示词，必须包含 {analysis_instruction} 占位符。',
        'content': """你是资深股票数据分析师。基于用户问题、SQL和查询结果，进行专业的数据分析。

字段说明：
- trade_date: 交易日期 (YYYY-MM-DD)
- open/high/low/close: 开/高/低/收盘价 (元)
- pct_chg: 涨跌幅 (%)
- change: 涨跌额 (元)
- vol: 成交量 (手)
- amount: 成交额 (千元)

分析指令：{analysis_instruction}

要求：
1. 使用 markdown 格式输出，包含标题、加粗、列表等
2. 涉及价格的数值保留两位小数，涨跌幅保留两位小数带%号
3. 不要虚构未出现在结果里的数字
4. 数据量少时直接给出结论，数据量多时做趋势和极值分析
5. 分析要有洞察，不只是罗列数字""",
    },
    'few_shot_examples': {
        'template_name': 'Few-shot 示例配置',
        'description': 'JSON 数组，每项包含 question 与 sql 字段。',
        'content': '[]',
    },
}


def _get_schema_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.schema_db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _get_app_conn() -> sqlite3.Connection:
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


def _to_page_result(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
    }


def _parse_detail(detail: str | None) -> dict[str, Any] | None:
    if not detail:
        return None
    try:
        return json.loads(detail)
    except json.JSONDecodeError:
        return {'raw': detail}


def init_admin_tables() -> None:
    with _get_schema_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_label TEXT,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_admin_action_log_created
            ON admin_action_log(created_at DESC);

            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_templates (
                template_key TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )

        for setting_key, definition in MODEL_SETTING_DEFINITIONS.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    setting_key,
                    str(definition['default']),
                    definition['description'],
                    _now_ts(),
                ),
            )

        for template_key, definition in PROMPT_TEMPLATE_DEFINITIONS.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO prompt_templates (template_key, template_name, content, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    template_key,
                    definition['template_name'],
                    definition['content'],
                    definition['description'],
                    _now_ts(),
                ),
            )

    with _get_app_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS query_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                sql_text TEXT,
                duration_ms INTEGER DEFAULT 0,
                from_cache INTEGER DEFAULT 0,
                chart_generated INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_query_audit_created
            ON query_audit(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_query_audit_user_created
            ON query_audit(username, created_at DESC);
            """
        )
        _ensure_column(conn, 'chat_sessions', 'is_pinned', 'INTEGER NOT NULL DEFAULT 0')


def get_runtime_model_settings() -> dict[str, Any]:
    runtime = {
        key: definition['default']
        for key, definition in MODEL_SETTING_DEFINITIONS.items()
    }
    with _get_schema_conn() as conn:
        rows = conn.execute(
            "SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN (?, ?, ?, ?, ?)",
            tuple(MODEL_SETTING_DEFINITIONS.keys()),
        ).fetchall()
    for row in rows:
        key = row['setting_key']
        value = row['setting_value']
        if key in {'timeout_seconds', 'retry_count', 'max_context_rounds'}:
            runtime[key] = int(value)
        else:
            runtime[key] = value
    return runtime


def update_runtime_model_settings(payload: dict[str, Any]) -> dict[str, Any]:
    updated_at = _now_ts()
    with _get_schema_conn() as conn:
        for key in MODEL_SETTING_DEFINITIONS:
            conn.execute(
                """
                INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    str(payload[key]),
                    MODEL_SETTING_DEFINITIONS[key]['description'],
                    updated_at,
                ),
            )
    return get_runtime_model_settings()


def get_prompt_templates() -> list[dict[str, Any]]:
    template_map = get_runtime_prompt_template_map()
    with _get_schema_conn() as conn:
        rows = conn.execute(
            """
            SELECT template_key, template_name, content, description, updated_at
            FROM prompt_templates
            ORDER BY template_key ASC
            """
        ).fetchall()
    existing = {row['template_key']: dict(row) for row in rows}
    items = []
    for key, definition in PROMPT_TEMPLATE_DEFINITIONS.items():
        item = existing.get(key, {
            'template_key': key,
            'template_name': definition['template_name'],
            'content': definition['content'],
            'description': definition['description'],
            'updated_at': None,
        })
        item['content'] = template_map[key]
        items.append(item)
    return items


def get_runtime_prompt_template_map() -> dict[str, str]:
    templates = {
        key: definition['content']
        for key, definition in PROMPT_TEMPLATE_DEFINITIONS.items()
    }
    with _get_schema_conn() as conn:
        rows = conn.execute(
            "SELECT template_key, content FROM prompt_templates WHERE template_key IN (?, ?, ?)",
            tuple(PROMPT_TEMPLATE_DEFINITIONS.keys()),
        ).fetchall()
    for row in rows:
        templates[row['template_key']] = row['content']
    return templates


def update_prompt_templates(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated_at = _now_ts()
    with _get_schema_conn() as conn:
        for template in templates:
            key = template['template_key']
            if key not in PROMPT_TEMPLATE_DEFINITIONS:
                continue
            conn.execute(
                """
                INSERT INTO prompt_templates (template_key, template_name, content, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(template_key) DO UPDATE SET
                    template_name = excluded.template_name,
                    content = excluded.content,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    template.get('template_name') or PROMPT_TEMPLATE_DEFINITIONS[key]['template_name'],
                    template['content'],
                    template.get('description') or PROMPT_TEMPLATE_DEFINITIONS[key]['description'],
                    updated_at,
                ),
            )
    return get_prompt_templates()


def log_admin_action(
    actor_username: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    target_label: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    with _get_schema_conn() as conn:
        conn.execute(
            """
            INSERT INTO admin_action_log (
                actor_username, actor_role, action, target_type, target_id, target_label, detail, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor_username,
                actor_role,
                action,
                target_type,
                target_id,
                target_label,
                json.dumps(detail, ensure_ascii=False) if detail else None,
                _now_ts(),
            ),
        )


def list_admin_action_logs(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if keyword:
        where_clauses.append("(actor_username LIKE ? OR action LIKE ? OR target_label LIKE ?)")
        like = f'%{keyword}%'
        params.extend([like, like, like])
    if start_time:
        where_clauses.append("created_at >= ?")
        params.append(start_time)
    if end_time:
        where_clauses.append("created_at <= ?")
        params.append(end_time)

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size
    with _get_schema_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM admin_action_log WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, actor_username, actor_role, action, target_type, target_id, target_label, detail, created_at
            FROM admin_action_log
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['detail'] = _parse_detail(item.get('detail'))
        items.append(item)
    return _to_page_result(items, total, page, page_size)


def list_admin_users(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if keyword:
        where_clauses.append("(username LIKE ? OR nickname LIKE ?)")
        like = f'%{keyword}%'
        params.extend([like, like])
    if role:
        where_clauses.append("role = ?")
        params.append(role)
    if status:
        where_clauses.append("status = ?")
        params.append(status)

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size
    with _get_schema_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM sys_user WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, username, nickname, role, status, login_attempts, locked_until, last_login_time, created_at
            FROM sys_user
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    return _to_page_result([dict(row) for row in rows], total, page, page_size)


def get_admin_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _get_schema_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, nickname, role, status, login_attempts, locked_until, last_login_time, created_at
            FROM sys_user
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def update_admin_user_status(user_id: int, status: str) -> dict[str, Any] | None:
    target = get_admin_user_by_id(user_id)
    if not target:
        return None
    if target['username'] == 'admin':
        raise ValueError('admin 用户的角色、状态和密码不可更改')
    with _get_schema_conn() as conn:
        conn.execute(
            "UPDATE sys_user SET status = ?, locked_until = CASE WHEN ? = 'active' THEN NULL ELSE locked_until END WHERE id = ?",
            (status, status, user_id),
        )
    return get_admin_user_by_id(user_id)


def update_admin_user_role(user_id: int, role: str, actor_role: str | None = None) -> dict[str, Any] | None:
    if role == 'superadmin':
        raise ValueError('不可为任何用户设置超级管理员角色')
    if role == 'admin' and actor_role != 'superadmin':
        raise ValueError('仅超级管理员可设置管理员角色')
    target = get_admin_user_by_id(user_id)
    if not target:
        return None
    if target['username'] == 'admin':
        raise ValueError('admin 用户的角色、状态和密码不可更改')
    with _get_schema_conn() as conn:
        conn.execute(
            "UPDATE sys_user SET role = ? WHERE id = ?",
            (role, user_id),
        )
    return get_admin_user_by_id(user_id)


def reset_admin_user_password(user_id: int) -> tuple[dict[str, Any] | None, str]:
    target = get_admin_user_by_id(user_id)
    if not target:
        return None, ''
    if target['username'] == 'admin':
        raise ValueError('admin 用户的角色、状态和密码不可更改')
    temporary_password = '123456'
    password_hash = bcrypt.hashpw(temporary_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with _get_schema_conn() as conn:
        conn.execute(
            "UPDATE sys_user SET password_hash = ?, login_attempts = 0, locked_until = NULL WHERE id = ?",
            (password_hash, user_id),
        )
    return get_admin_user_by_id(user_id), temporary_password


def list_admin_login_logs(
    page: int = 1,
    page_size: int = 20,
    username: str | None = None,
    success: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if username:
        where_clauses.append("username LIKE ?")
        params.append(f'%{username}%')
    if success is not None:
        where_clauses.append("success = ?")
        params.append(success)
    if start_time:
        where_clauses.append("created_at >= ?")
        params.append(start_time)
    if end_time:
        where_clauses.append("created_at <= ?")
        params.append(end_time)

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size
    with _get_schema_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM sys_login_log WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, username, success, ip_address, user_agent, created_at
            FROM sys_login_log
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    return _to_page_result([dict(row) for row in rows], total, page, page_size)


def list_admin_sessions(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    user_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    is_pinned: bool | None = None,
) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if user_id:
        where_clauses.append("s.user_id LIKE ?")
        params.append(f'%{user_id}%')
    if start_time:
        where_clauses.append("s.created_at >= ?")
        params.append(start_time)
    if end_time:
        where_clauses.append("s.created_at <= ?")
        params.append(end_time)
    if is_pinned is not None:
        where_clauses.append("s.is_pinned = ?")
        params.append(1 if is_pinned else 0)
    if keyword:
        like = f'%{keyword}%'
        where_clauses.append(
            """
            (
                s.title LIKE ?
                OR EXISTS (
                    SELECT 1 FROM chat_messages m
                    WHERE m.session_id = s.session_id
                      AND (m.content LIKE ? OR IFNULL(m.sql_text, '') LIKE ?)
                )
            )
            """
        )
        params.extend([like, like, like])

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size
    with _get_app_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM chat_sessions s WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT
                s.session_id,
                s.user_id,
                s.title,
                s.created_at,
                s.updated_at,
                s.is_pinned,
                COUNT(m.id) AS message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.session_id
            WHERE {where_sql}
            GROUP BY s.session_id, s.user_id, s.title, s.created_at, s.updated_at, s.is_pinned
            ORDER BY s.is_pinned DESC, s.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['is_pinned'] = bool(item.get('is_pinned'))
        items.append(item)
    return _to_page_result(items, total, page, page_size)


def get_admin_session_detail(session_id: str) -> dict[str, Any] | None:
    with _get_app_conn() as conn:
        session = conn.execute(
            """
            SELECT session_id, user_id, title, created_at, updated_at, is_pinned
            FROM chat_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if not session:
            return None
        message_count = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        messages = conn.execute(
            """
            SELECT id, role, content, sql_text, result_preview, chart_path, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    session_dict = dict(session)
    session_dict['is_pinned'] = bool(session_dict.get('is_pinned'))
    session_dict['message_count'] = message_count
    return {
        'session': session_dict,
        'messages': [dict(row) for row in messages],
    }


def delete_admin_session(session_id: str) -> bool:
    with _get_app_conn() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM query_audit WHERE session_id = ?", (session_id,))
        history_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'chat_messages_langchain'"
        ).fetchone()
        if history_table:
            conn.execute("DELETE FROM chat_messages_langchain WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        return cursor.rowcount > 0


def set_session_pinned(session_id: str, is_pinned: bool) -> bool:
    with _get_app_conn() as conn:
        cursor = conn.execute(
            "UPDATE chat_sessions SET is_pinned = ?, updated_at = ? WHERE session_id = ?",
            (1 if is_pinned else 0, _now_ts(), session_id),
        )
        return cursor.rowcount > 0


def record_query_audit(
    username: str,
    session_id: str,
    question: str,
    sql_text: str | None,
    duration_ms: int,
    from_cache: bool,
    chart_generated: bool,
    status: str,
    error_message: str | None = None,
) -> None:
    with _get_app_conn() as conn:
        conn.execute(
            """
            INSERT INTO query_audit (
                username, session_id, question, sql_text, duration_ms, from_cache,
                chart_generated, status, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                session_id,
                question,
                sql_text,
                duration_ms,
                1 if from_cache else 0,
                1 if chart_generated else 0,
                status,
                error_message,
                _now_ts(),
            ),
        )


def list_query_audits(
    page: int = 1,
    page_size: int = 20,
    username: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    where_clauses = ["1=1"]
    params: list[Any] = []
    if username:
        where_clauses.append("username LIKE ?")
        params.append(f'%{username}%')
    if session_id:
        where_clauses.append("session_id LIKE ?")
        params.append(f'%{session_id}%')
    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if keyword:
        like = f'%{keyword}%'
        where_clauses.append("(question LIKE ? OR IFNULL(sql_text, '') LIKE ? OR IFNULL(error_message, '') LIKE ?)")
        params.extend([like, like, like])
    if start_time:
        where_clauses.append("created_at >= ?")
        params.append(start_time)
    if end_time:
        where_clauses.append("created_at <= ?")
        params.append(end_time)

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * page_size
    with _get_app_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM query_audit WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, username, session_id, question, sql_text, duration_ms, from_cache,
                   chart_generated, status, error_message, created_at
            FROM query_audit
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['from_cache'] = bool(item.get('from_cache'))
        item['chart_generated'] = bool(item.get('chart_generated'))
        items.append(item)
    return _to_page_result(items, total, page, page_size)


def create_admin_user(
    username: str | None = None,
    password: str | None = None,
    nickname: str | None = None,
) -> dict[str, Any]:
    """创建新用户，默认用户名为 user+自增序号，默认密码为 123456"""
    import re

    if username is not None:
        if not re.fullmatch(r'^[a-zA-Z0-9]+$', username):
            raise ValueError('用户名仅支持数字加英文')
        if len(username) < 1 or len(username) > 8:
            raise ValueError('用户名长度为1-8位')

    if password is not None:
        if not re.fullmatch(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]+$', password):
            raise ValueError('密码仅支持英文加数字加符号')
        if len(password) > 12:
            raise ValueError('密码最多12位')

    with _get_schema_conn() as conn:
        if username is not None:
            existing = conn.execute(
                "SELECT id FROM sys_user WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                raise ValueError(f'用户名 {username} 已存在')

    if username is None:
        with _get_schema_conn() as conn:
            rows = conn.execute(
                "SELECT username FROM sys_user WHERE username GLOB 'user[0-9]*'"
            ).fetchall()

        max_seq = 0
        for row in rows:
            match = re.match(r'^user(\d+)$', row['username'])
            if match:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq

        new_username = f'user{max_seq + 1}'
    else:
        new_username = username

    user_password = password if password else '123456'
    password_hash = bcrypt.hashpw(user_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    with _get_schema_conn() as conn:
        now = _now_ts()
        conn.execute(
            """
            INSERT INTO sys_user (username, password_hash, nickname, role, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_username, password_hash, nickname or new_username, 'user', 'active', now),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return {
        'id': user_id,
        'username': new_username,
        'nickname': nickname or new_username,
        'role': 'user',
        'status': 'active',
        'login_attempts': 0,
        'locked_until': None,
        'last_login_time': None,
        'created_at': now,
    }


def get_admin_overview() -> dict[str, Any]:
    today_prefix = datetime.now().strftime('%Y-%m-%d')
    with _get_schema_conn() as schema_conn, _get_app_conn() as app_conn:
        total_users = schema_conn.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0]
        active_users = schema_conn.execute("SELECT COUNT(*) FROM sys_user WHERE status = 'active'").fetchone()[0]
        today_logins = schema_conn.execute(
            "SELECT COUNT(*) FROM sys_login_log WHERE created_at >= ?",
            (today_prefix,),
        ).fetchone()[0]
        failed_logins = schema_conn.execute(
            "SELECT COUNT(*) FROM sys_login_log WHERE success = 0 AND created_at >= ?",
            (today_prefix,),
        ).fetchone()[0]
        total_sessions = app_conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
        recent_login_logs = schema_conn.execute(
            """
            SELECT id, username, success, ip_address, user_agent, created_at
            FROM sys_login_log
            ORDER BY created_at DESC, id DESC
            LIMIT 10
            """
        ).fetchall()
        recent_failures = app_conn.execute(
            """
            SELECT id, username, session_id, question, sql_text, duration_ms, from_cache,
                   chart_generated, status, error_message, created_at
            FROM query_audit
            WHERE status != 'success'
            ORDER BY created_at DESC, id DESC
            LIMIT 10
            """
        ).fetchall()

    return {
        'stats': {
            'today_logins': today_logins,
            'total_users': total_users,
            'active_users': active_users,
            'total_sessions': total_sessions,
            'failed_logins': failed_logins,
        },
        'recent_login_logs': [dict(row) for row in recent_login_logs],
        'recent_failures': [
            {
                **dict(row),
                'from_cache': bool(row['from_cache']),
                'chart_generated': bool(row['chart_generated']),
            }
            for row in recent_failures
        ],
    }
