import hashlib
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from backend.config import settings

SECRET_KEY = settings.dashscope_api_key or hashlib.sha256(os.urandom(32)).hexdigest()
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15

ROLES = {
    'superadmin': '超级管理员',
    'admin': '管理员',
    'user': '普通用户',
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.schema_db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _now_ts() -> str:
    return datetime.now().isoformat(timespec='seconds')


def init_auth_tables() -> None:
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sys_user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nickname TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                login_attempts INTEGER DEFAULT 0,
                locked_until TEXT,
                last_login_time TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sys_login_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                success INTEGER DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM sys_user WHERE username = ?",
            ('admin',),
        ).fetchone()
        if not existing:
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute(
                """
                INSERT INTO sys_user (username, password_hash, nickname, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ('admin', password_hash, '系统管理员', 'admin', 'active', _now_ts()),
            )

        existing_user = conn.execute(
            "SELECT id FROM sys_user WHERE username = ?",
            ('user',),
        ).fetchone()
        if not existing_user:
            password_hash = bcrypt.hashpw('user123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute(
                """
                INSERT INTO sys_user (username, password_hash, nickname, role, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ('user', password_hash, '普通用户', 'user', 'active', _now_ts()),
            )


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, nickname, role, status, login_attempts, locked_until, last_login_time, created_at
            FROM sys_user
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, nickname, role, status, login_attempts, locked_until, last_login_time, created_at
            FROM sys_user
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_runtime_user_context(username: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if not user or user.get('status') != 'active':
        return None
    return {
        'id': user['id'],
        'sub': user['username'],
        'username': user['username'],
        'nickname': user.get('nickname') or user['username'],
        'role': user['role'],
        'status': user['status'],
        'last_login_time': user.get('last_login_time'),
    }


def authenticate_user(
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any] | None:
    with _get_conn() as conn:
        user = conn.execute(
            """
            SELECT id, username, password_hash, nickname, role, status, login_attempts, locked_until, last_login_time
            FROM sys_user
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        if not user:
            _log_login(username, False, ip_address, user_agent)
            return None

        if user['status'] != 'active':
            _log_login(username, False, ip_address, user_agent, conn)
            return None

        if user['locked_until'] and user['locked_until'] > _now_ts():
            _log_login(username, False, ip_address, user_agent, conn)
            return None

        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            attempts = user['login_attempts'] + 1
            locked_until = None
            if attempts >= MAX_LOGIN_ATTEMPTS:
                locked_until = (datetime.now() + timedelta(minutes=LOGIN_LOCK_MINUTES)).isoformat(timespec='seconds')
            conn.execute(
                "UPDATE sys_user SET login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, user['id']),
            )
            _log_login(username, False, ip_address, user_agent, conn)
            return None

        conn.execute(
            """
            UPDATE sys_user
            SET login_attempts = 0, locked_until = NULL, last_login_time = ?
            WHERE id = ?
            """,
            (_now_ts(), user['id']),
        )
        _log_login(username, True, ip_address, user_agent, conn)
        return {
            'id': user['id'],
            'username': user['username'],
            'nickname': user['nickname'],
            'role': user['role'],
            'status': user['status'],
        }


def create_access_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        'sub': username,
        'role': role,
        'exp': expire,
        'type': 'access',
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        'sub': username,
        'role': role,
        'exp': expire,
        'type': 'refresh',
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _log_login(
    username: str,
    success: bool,
    ip_address: str | None = None,
    user_agent: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    sql = """
        INSERT INTO sys_login_log (username, success, ip_address, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?)
    """
    params = (username, 1 if success else 0, ip_address, user_agent, _now_ts())
    if conn:
        conn.execute(sql, params)
        return
    with _get_conn() as current:
        current.execute(sql, params)

