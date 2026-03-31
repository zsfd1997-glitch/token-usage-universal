#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from team_common import build_time_window, coerce_datetime, effective_tokens, resolve_tz


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "team_usage.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_text() -> str:
    return utc_now().isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def db_connect(db_path: Path) -> sqlite3.Connection:
    _ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: Path) -> None:
    conn = db_connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS web_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token_hash TEXT NOT NULL UNIQUE,
                admin_user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (admin_user_id) REFERENCES admin_users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_prefix TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                machine_label TEXT,
                note TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                machine_label TEXT,
                source TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT,
                session_id TEXT NOT NULL,
                project_path TEXT,
                timestamp TEXT NOT NULL,
                day TEXT NOT NULL,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_tokens INTEGER,
                total_tokens INTEGER NOT NULL,
                effective_tokens INTEGER NOT NULL,
                accuracy_level TEXT NOT NULL,
                raw_event_kind TEXT NOT NULL,
                source_path TEXT NOT NULL,
                exported_at TEXT,
                ingested_at TEXT NOT NULL,
                agent_token_id INTEGER,
                FOREIGN KEY (agent_token_id) REFERENCES agent_tokens(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_events_team_time
                ON usage_events(team_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_events_team_day
                ON usage_events(team_id, day);
            CREATE INDEX IF NOT EXISTS idx_usage_events_team_user
                ON usage_events(team_id, user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_events_team_machine
                ON usage_events(team_id, machine_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_events_team_source
                ON usage_events(team_id, source, timestamp);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        240_000,
    ).hex()


def create_admin_user(db_path: Path, username: str, password: str) -> dict[str, Any]:
    conn = db_connect(db_path)
    try:
        salt = secrets.token_hex(16)
        password_hash = _hash_password(password, salt)
        conn.execute(
            "INSERT INTO admin_users(username, password_salt, password_hash, created_at) VALUES(?, ?, ?, ?)",
            (username, salt, password_hash, utc_now_text()),
        )
        conn.commit()
        return {"username": username, "created": True}
    finally:
        conn.close()


def authenticate_admin_user(db_path: Path, username: str, password: str) -> sqlite3.Row | None:
    conn = db_connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, username, password_salt, password_hash FROM admin_users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        candidate = _hash_password(password, row["password_salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return None
        return row
    finally:
        conn.close()


def create_web_session(db_path: Path, admin_user_id: int, *, ttl_hours: int = 12) -> str:
    conn = db_connect(db_path)
    try:
        token = secrets.token_urlsafe(32)
        expires_at = (utc_now() + timedelta(hours=ttl_hours)).isoformat()
        now_text = utc_now_text()
        conn.execute(
            "INSERT INTO web_sessions(session_token_hash, admin_user_id, expires_at, created_at, last_seen_at) VALUES(?, ?, ?, ?, ?)",
            (_hash_secret(token), admin_user_id, expires_at, now_text, now_text),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def delete_web_session(db_path: Path, token: str | None) -> None:
    if not token:
        return
    conn = db_connect(db_path)
    try:
        conn.execute("DELETE FROM web_sessions WHERE session_token_hash = ?", (_hash_secret(token),))
        conn.commit()
    finally:
        conn.close()


def authenticate_session(db_path: Path, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    conn = db_connect(db_path)
    try:
        now_text = utc_now_text()
        conn.execute("DELETE FROM web_sessions WHERE expires_at < ?", (now_text,))
        row = conn.execute(
            """
            SELECT web_sessions.id, web_sessions.admin_user_id, admin_users.username
            FROM web_sessions
            JOIN admin_users ON admin_users.id = web_sessions.admin_user_id
            WHERE web_sessions.session_token_hash = ? AND web_sessions.expires_at >= ?
            """,
            (_hash_secret(token), now_text),
        ).fetchone()
        if row:
            conn.execute("UPDATE web_sessions SET last_seen_at = ? WHERE id = ?", (now_text, row["id"]))
            conn.commit()
        return row
    finally:
        conn.close()


def issue_agent_token(db_path: Path, *, team_id: str, user_id: str, machine_id: str, machine_label: str | None, note: str | None) -> dict[str, Any]:
    conn = db_connect(db_path)
    try:
        raw_token = f"tuat_{secrets.token_urlsafe(24)}"
        conn.execute(
            """
            INSERT INTO agent_tokens(
                token_prefix, token_hash, team_id, user_id, machine_id, machine_label, note, enabled, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                raw_token[:10],
                _hash_secret(raw_token),
                team_id,
                user_id,
                machine_id,
                machine_label,
                note,
                utc_now_text(),
            ),
        )
        conn.commit()
        return {
            "token": raw_token,
            "team_id": team_id,
            "user_id": user_id,
            "machine_id": machine_id,
            "machine_label": machine_label,
            "note": note,
        }
    finally:
        conn.close()


def authenticate_agent_token(db_path: Path, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    conn = db_connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, team_id, user_id, machine_id, machine_label, enabled
            FROM agent_tokens
            WHERE token_hash = ? AND enabled = 1
            """,
            (_hash_secret(token),),
        ).fetchone()
        if row:
            conn.execute("UPDATE agent_tokens SET last_seen_at = ? WHERE id = ?", (utc_now_text(), row["id"]))
            conn.commit()
        return row
    finally:
        conn.close()


def _normalize_event_for_storage(payload: dict[str, Any], agent_row: sqlite3.Row) -> dict[str, Any]:
    timestamp = coerce_datetime(str(payload["timestamp"]), None).astimezone(timezone.utc)
    day = timestamp.astimezone(resolve_tz("Asia/Shanghai")).strftime("%Y-%m-%d")
    total = int(payload["total_tokens"])
    cached = int(payload.get("cached_input_tokens") or 0)
    return {
        "event_id": str(payload["event_id"]),
        "team_id": str(agent_row["team_id"]),
        "user_id": str(agent_row["user_id"]),
        "machine_id": str(agent_row["machine_id"]),
        "machine_label": payload.get("machine_label") or agent_row["machine_label"] or agent_row["machine_id"],
        "source": str(payload["source"]),
        "provider": str(payload["provider"]),
        "model": payload.get("model"),
        "session_id": str(payload["session_id"]),
        "project_path": payload.get("project_path"),
        "timestamp": timestamp.isoformat(),
        "day": day,
        "input_tokens": int(payload["input_tokens"]) if payload.get("input_tokens") is not None else None,
        "cached_input_tokens": cached,
        "output_tokens": int(payload["output_tokens"]) if payload.get("output_tokens") is not None else None,
        "reasoning_tokens": int(payload["reasoning_tokens"]) if payload.get("reasoning_tokens") is not None else None,
        "total_tokens": total,
        "effective_tokens": effective_tokens(total, cached),
        "accuracy_level": str(payload["accuracy_level"]),
        "raw_event_kind": str(payload["raw_event_kind"]),
        "source_path": str(payload["source_path"]),
        "exported_at": payload.get("exported_at"),
        "ingested_at": utc_now_text(),
        "agent_token_id": int(agent_row["id"]),
    }


def ingest_events(db_path: Path, agent_row: sqlite3.Row, events: list[dict[str, Any]]) -> dict[str, Any]:
    conn = db_connect(db_path)
    inserted = 0
    duplicates = 0
    try:
        for payload in events:
            record = _normalize_event_for_storage(payload, agent_row)
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO usage_events(
                    event_id, team_id, user_id, machine_id, machine_label, source, provider, model,
                    session_id, project_path, timestamp, day, input_tokens, cached_input_tokens,
                    output_tokens, reasoning_tokens, total_tokens, effective_tokens, accuracy_level,
                    raw_event_kind, source_path, exported_at, ingested_at, agent_token_id
                ) VALUES(
                    :event_id, :team_id, :user_id, :machine_id, :machine_label, :source, :provider, :model,
                    :session_id, :project_path, :timestamp, :day, :input_tokens, :cached_input_tokens,
                    :output_tokens, :reasoning_tokens, :total_tokens, :effective_tokens, :accuracy_level,
                    :raw_event_kind, :source_path, :exported_at, :ingested_at, :agent_token_id
                )
                """,
                record,
            )
            if cursor.rowcount:
                inserted += 1
            else:
                duplicates += 1
        conn.commit()
        return {"received": len(events), "inserted": inserted, "duplicates": duplicates}
    finally:
        conn.close()


def list_teams(db_path: Path) -> list[str]:
    conn = db_connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT team_id FROM usage_events ORDER BY team_id").fetchall()
        return [row["team_id"] for row in rows]
    finally:
        conn.close()


def _window_clause(window) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if window.start:
        clauses.append("timestamp >= ?")
        params.append(window.start.astimezone(timezone.utc).isoformat())
    if window.end:
        clauses.append("timestamp <= ?")
        params.append(window.end.astimezone(timezone.utc).isoformat())
    return (" AND ".join(clauses), params)


def _query_summary(conn: sqlite3.Connection, team_id: str, window) -> dict[str, Any]:
    clause, params = _window_clause(window)
    sql = """
        SELECT
            COUNT(*) AS events,
            COUNT(DISTINCT user_id) AS users,
            COUNT(DISTINCT machine_id) AS machines,
            COUNT(DISTINCT project_path) AS projects,
            COUNT(DISTINCT session_id) AS sessions,
            COUNT(DISTINCT source) AS sources,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
            COALESCE(SUM(effective_tokens), 0) AS effective_tokens
        FROM usage_events
        WHERE team_id = ?
    """
    values: list[Any] = [team_id]
    if clause:
        sql += f" AND {clause}"
        values.extend(params)
    row = conn.execute(sql, values).fetchone()
    return dict(row) if row else {}


def _group_column(group_by: str) -> str:
    mapping = {
        "user": "user_id",
        "machine": "machine_id",
        "project": "COALESCE(project_path, '(unknown project)')",
        "model": "COALESCE(model, '(unknown model)')",
        "source": "source",
        "day": "day",
    }
    if group_by not in mapping:
        raise ValueError(f"unsupported group_by: {group_by}")
    return mapping[group_by]


def _query_grouped(conn: sqlite3.Connection, team_id: str, window, group_by: str, limit: int) -> list[dict[str, Any]]:
    column = _group_column(group_by)
    clause, params = _window_clause(window)
    sql = f"""
        SELECT
            {column} AS name,
            COUNT(*) AS events,
            COUNT(DISTINCT user_id) AS users,
            COUNT(DISTINCT machine_id) AS machines,
            COUNT(DISTINCT source) AS sources,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
            COALESCE(SUM(effective_tokens), 0) AS effective_tokens,
            MAX(timestamp) AS last_timestamp
        FROM usage_events
        WHERE team_id = ?
    """
    values: list[Any] = [team_id]
    if clause:
        sql += f" AND {clause}"
        values.extend(params)
    sql += """
        GROUP BY name
        ORDER BY effective_tokens DESC, total_tokens DESC, events DESC
        LIMIT ?
    """
    values.append(limit)
    rows = conn.execute(sql, values).fetchall()
    return [dict(row) for row in rows]


def _query_recent_events(conn: sqlite3.Connection, team_id: str, window, limit: int) -> list[dict[str, Any]]:
    clause, params = _window_clause(window)
    sql = """
        SELECT
            timestamp, user_id, machine_id, source, model, project_path,
            total_tokens, effective_tokens, cached_input_tokens, session_id
        FROM usage_events
        WHERE team_id = ?
    """
    values: list[Any] = [team_id]
    if clause:
        sql += f" AND {clause}"
        values.extend(params)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    values.append(limit)
    rows = conn.execute(sql, values).fetchall()
    return [dict(row) for row in rows]


def _query_agents(conn: sqlite3.Connection, team_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT user_id, machine_id, machine_label, note, enabled, created_at, last_seen_at
        FROM agent_tokens
        WHERE team_id = ?
        ORDER BY user_id, machine_id
        """,
        (team_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def build_dashboard_payload(db_path: Path, *, team_id: str, window, limit: int = 8) -> dict[str, Any]:
    conn = db_connect(db_path)
    try:
        payload = {
            "team_id": team_id,
            "window": {
                "label": window.label,
                "start": window.start.isoformat() if window.start else None,
                "end": window.end.isoformat() if window.end else None,
                "timezone": window.timezone_name,
            },
            "summary": _query_summary(conn, team_id, window),
            "by_user": _query_grouped(conn, team_id, window, "user", limit),
            "by_machine": _query_grouped(conn, team_id, window, "machine", limit),
            "by_project": _query_grouped(conn, team_id, window, "project", limit),
            "by_model": _query_grouped(conn, team_id, window, "model", limit),
            "by_source": _query_grouped(conn, team_id, window, "source", limit),
            "trend": _query_grouped(conn, team_id, window, "day", 30),
            "recent_events": _query_recent_events(conn, team_id, window, 20),
            "agents": _query_agents(conn, team_id),
            "available_teams": list_teams(db_path),
        }
        return payload
    finally:
        conn.close()


LOGIN_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Token Usage Team Edition</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #eef3eb;
      --card: #ffffff;
      --ink: #17211b;
      --muted: #66756b;
      --accent: #0e8a63;
      --line: #d8e1da;
      --shadow: 0 18px 40px rgba(23, 33, 27, 0.08);
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(14, 138, 99, 0.14), transparent 28%),
        linear-gradient(160deg, #f7fbf8, var(--bg));
      min-height: 100vh;
      display: grid;
      place-items: center;
    }
    .card {
      width: min(92vw, 420px);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 28px;
    }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { margin: 0 0 20px; color: var(--muted); line-height: 1.6; }
    label { display: block; font-size: 14px; margin-bottom: 6px; color: var(--muted); }
    input {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      margin-bottom: 16px;
      font-size: 15px;
      background: #f9fbf9;
    }
    button {
      width: 100%;
      border: 0;
      border-radius: 14px;
      padding: 13px 16px;
      font-size: 15px;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, #0e8a63, #1f6d91);
      cursor: pointer;
    }
    .hint { margin-top: 14px; font-size: 13px; color: var(--muted); }
    .error { color: #b42318; margin-bottom: 12px; font-size: 14px; }
  </style>
</head>
<body>
  <form class="card" method="post" action="/login">
    <h1>团队后台登录</h1>
    <p>纯内网账号体系，不依赖百度、钉钉或其他外部登录。</p>
    __ERROR_BLOCK__
    <label>用户名</label>
    <input name="username" autocomplete="username" required />
    <label>密码</label>
    <input name="password" type="password" autocomplete="current-password" required />
    <button type="submit">登录后台</button>
    <div class="hint">管理员账号请用 `create-admin` 命令提前创建。</div>
  </form>
</body>
</html>
"""


DASHBOARD_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Token Usage Team Edition Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #f3f7f0;
      --panel: #ffffff;
      --ink: #18221b;
      --muted: #617066;
      --accent: #0c8f67;
      --accent-2: #1f6d91;
      --line: #d8e0d8;
      --shadow: 0 22px 50px rgba(18, 29, 23, 0.08);
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 0% 0%, rgba(12, 143, 103, 0.12), transparent 35%),
        radial-gradient(circle at 100% 0%, rgba(31, 109, 145, 0.12), transparent 30%),
        linear-gradient(180deg, #fbfdfb, var(--bg));
    }
    .wrap { max-width: 1280px; margin: 0 auto; padding: 28px 20px 40px; }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 22px;
    }
    .title h1 { margin: 0; font-size: 34px; }
    .title p { margin: 8px 0 0; color: var(--muted); }
    .logout {
      text-decoration: none;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255,255,255,0.8);
    }
    .toolbar, .panel, .card {
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 22px;
    }
    .toolbar {
      padding: 16px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .toolbar label { font-size: 13px; color: var(--muted); display: block; margin-bottom: 6px; }
    .toolbar select, .toolbar button {
      width: 100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fafcf9;
      font-size: 14px;
    }
    .toolbar button {
      align-self: end;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: white;
      border: 0;
      font-weight: 700;
      cursor: pointer;
      margin-top: 19px;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .card { padding: 18px; }
    .card .label { font-size: 13px; color: var(--muted); margin-bottom: 10px; }
    .card .value { font-size: 30px; font-weight: 800; letter-spacing: -0.02em; }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
    }
    .stack { display: grid; gap: 16px; }
    .panel { padding: 18px; }
    .panel h2 { margin: 0 0 14px; font-size: 19px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 10px 0; border-bottom: 1px solid #edf1ec; font-size: 14px; }
    th { color: var(--muted); font-weight: 600; font-size: 13px; }
    .bar-row { display: grid; grid-template-columns: 120px 1fr 90px; gap: 12px; align-items: center; margin: 10px 0; }
    .bar-shell { height: 10px; border-radius: 999px; background: #ecf2ed; overflow: hidden; }
    .bar { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }
    .muted { color: var(--muted); }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #edf7f2; color: #0c8f67; font-size: 12px; }
    .footer-note { margin-top: 16px; color: var(--muted); font-size: 13px; }
    @media (max-width: 1024px) {
      .toolbar, .cards, .grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 720px) {
      .toolbar, .cards, .grid { grid-template-columns: 1fr; }
      .topbar { display: block; }
      .logout { display: inline-block; margin-top: 12px; }
      .bar-row { grid-template-columns: 100px 1fr 70px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="title">
        <h1>团队 Token 后台</h1>
        <p id="welcome">正在加载团队信息…</p>
      </div>
      <a class="logout" href="/logout">退出登录</a>
    </div>

    <div class="toolbar">
      <div>
        <label>团队</label>
        <select id="teamSelect"></select>
      </div>
      <div>
        <label>时间范围</label>
        <select id="rangeSelect">
          <option value="today">今天</option>
          <option value="7d" selected>最近 7 天</option>
          <option value="30d">最近 30 天</option>
        </select>
      </div>
      <div>
        <label>排序展示数量</label>
        <select id="limitSelect">
          <option value="5">5</option>
          <option value="8" selected>8</option>
          <option value="12">12</option>
        </select>
      </div>
      <div>
        <button id="refreshBtn" type="button">刷新数据</button>
      </div>
    </div>

    <div class="cards" id="cards"></div>

    <div class="grid">
      <div class="stack">
        <section class="panel">
          <h2>按成员</h2>
          <div id="byUser"></div>
        </section>
        <section class="panel">
          <h2>按项目</h2>
          <div id="byProject"></div>
        </section>
        <section class="panel">
          <h2>最近事件</h2>
          <div id="recentEvents"></div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <h2>每日趋势</h2>
          <div id="trend"></div>
        </section>
        <section class="panel">
          <h2>按来源</h2>
          <div id="bySource"></div>
        </section>
        <section class="panel">
          <h2>在线设备令牌</h2>
          <div id="agents"></div>
          <div class="footer-note">设备由 `issue-agent-token` 创建，客户端使用 `team_agent.py run` 自动上报。</div>
        </section>
      </div>
    </div>
  </div>

  <script>
    let cachedMe = null;

    function number(value) {
      return new Intl.NumberFormat('zh-CN').format(Number(value || 0));
    }

    function barList(targetId, rows, metricKey, labelKey='name') {
      const target = document.getElementById(targetId);
      if (!rows || !rows.length) {
        target.innerHTML = '<div class="muted">当前没有数据。</div>';
        return;
      }
      const max = Math.max(...rows.map(item => Number(item[metricKey] || 0)), 1);
      target.innerHTML = rows.map(item => {
        const width = Math.max(8, Math.round(Number(item[metricKey] || 0) / max * 100));
        return `
          <div class="bar-row">
            <div>${item[labelKey]}</div>
            <div class="bar-shell"><div class="bar" style="width:${width}%"></div></div>
            <div>${number(item[metricKey])}</div>
          </div>
        `;
      }).join('');
    }

    function renderCards(summary) {
      const cards = [
        ['有效 Token', summary.effective_tokens],
        ['总 Token', summary.total_tokens],
        ['活跃成员', summary.users],
        ['活跃设备', summary.machines],
        ['项目数', summary.projects],
        ['会话数', summary.sessions],
        ['事件数', summary.events],
        ['来源数', summary.sources],
      ];
      document.getElementById('cards').innerHTML = cards.map(([label, value]) => `
        <div class="card">
          <div class="label">${label}</div>
          <div class="value">${number(value)}</div>
        </div>
      `).join('');
    }

    function renderRecent(rows) {
      const target = document.getElementById('recentEvents');
      if (!rows || !rows.length) {
        target.innerHTML = '<div class="muted">当前没有事件。</div>';
        return;
      }
      target.innerHTML = `
        <table>
          <thead><tr><th>时间</th><th>成员</th><th>来源</th><th>项目</th><th>有效 Token</th></tr></thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                <td>${row.timestamp.replace('T', ' ').slice(0, 16)}</td>
                <td>${row.user_id}<div class="muted">${row.machine_id}</div></td>
                <td><span class="pill">${row.source}</span></td>
                <td>${row.project_path || '(unknown project)'}</td>
                <td>${number(row.effective_tokens)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    function renderAgents(rows) {
      const target = document.getElementById('agents');
      if (!rows || !rows.length) {
        target.innerHTML = '<div class="muted">还没有签发设备令牌。</div>';
        return;
      }
      target.innerHTML = `
        <table>
          <thead><tr><th>成员</th><th>设备</th><th>最近心跳</th></tr></thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                <td>${row.user_id}</td>
                <td>${row.machine_label || row.machine_id}<div class="muted">${row.note || ''}</div></td>
                <td>${row.last_seen_at ? row.last_seen_at.replace('T', ' ').slice(0, 16) : '还未上报'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    async function fetchJson(path, options={}) {
      const response = await fetch(path, { credentials: 'include', ...options });
      if (response.status === 401) {
        window.location.href = '/login';
        return null;
      }
      if (!response.ok) {
        const payload = await response.json().catch(() => ({error: response.statusText}));
        throw new Error(payload.error || response.statusText);
      }
      return response.json();
    }

    async function loadMe() {
      cachedMe = await fetchJson('/api/me');
      if (!cachedMe) return;
      document.getElementById('welcome').textContent = `已登录：${cachedMe.username} · 纯内网部署 · 自动刷新`;
      const teamSelect = document.getElementById('teamSelect');
      teamSelect.innerHTML = cachedMe.teams.map(team => `<option value="${team}">${team}</option>`).join('');
      if (!cachedMe.teams.length) {
        teamSelect.innerHTML = '<option value="">(暂无团队数据)</option>';
      }
      await loadDashboard();
    }

    async function loadDashboard() {
      const teamId = document.getElementById('teamSelect').value;
      if (!teamId) {
        renderCards({effective_tokens: 0, total_tokens: 0, users: 0, machines: 0, projects: 0, sessions: 0, events: 0, sources: 0});
        document.getElementById('byUser').innerHTML = '<div class="muted">还没有上报数据。</div>';
        document.getElementById('byProject').innerHTML = '<div class="muted">还没有上报数据。</div>';
        document.getElementById('bySource').innerHTML = '<div class="muted">还没有上报数据。</div>';
        document.getElementById('trend').innerHTML = '<div class="muted">还没有上报数据。</div>';
        document.getElementById('recentEvents').innerHTML = '<div class="muted">还没有上报数据。</div>';
        document.getElementById('agents').innerHTML = '<div class="muted">还没有签发设备令牌。</div>';
        return;
      }
      const range = document.getElementById('rangeSelect').value;
      const limit = document.getElementById('limitSelect').value;
      const query = new URLSearchParams({ team_id: teamId, range, limit });
      const payload = await fetchJson(`/api/dashboard?${query.toString()}`);
      if (!payload) return;
      renderCards(payload.summary);
      barList('byUser', payload.by_user, 'effective_tokens');
      barList('byProject', payload.by_project, 'effective_tokens');
      barList('bySource', payload.by_source, 'effective_tokens');
      barList('trend', payload.trend, 'effective_tokens');
      renderRecent(payload.recent_events);
      renderAgents(payload.agents);
    }

    document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
    document.getElementById('teamSelect').addEventListener('change', loadDashboard);
    document.getElementById('rangeSelect').addEventListener('change', loadDashboard);
    document.getElementById('limitSelect').addEventListener('change', loadDashboard);
    setInterval(loadDashboard, 60000);
    loadMe();
  </script>
</body>
</html>
"""


class TeamHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, *, db_path: Path):
        super().__init__(server_address, RequestHandlerClass)
        self.db_path = db_path
        self.lock = threading.Lock()


class TeamRequestHandler(BaseHTTPRequestHandler):
    server: TeamHTTPServer

    def _cookies(self) -> cookies.SimpleCookie:
        jar = cookies.SimpleCookie()
        raw = self.headers.get("Cookie")
        if raw:
            jar.load(raw)
        return jar

    def _session_token(self) -> str | None:
        jar = self._cookies()
        morsel = jar.get("team_session")
        return morsel.value if morsel else None

    def _current_admin(self) -> sqlite3.Row | None:
        return authenticate_session(self.server.db_path, self._session_token())

    def _read_form_body(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        payload = parse_qs(raw)
        return {key: value[0] for key, value in payload.items()}

    def _read_json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _send_json(self, payload: Any, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location: str, *, headers: dict[str, str] | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()

    def _require_admin_json(self) -> sqlite3.Row | None:
        admin = self._current_admin()
        if not admin:
            self._send_json({"error": "unauthorized"}, status=401)
            return None
        return admin

    def _require_admin_page(self) -> sqlite3.Row | None:
        admin = self._current_admin()
        if not admin:
            self._redirect("/login")
            return None
        return admin

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            if self._current_admin():
                self._redirect("/dashboard")
            else:
                self._redirect("/login")
            return
        if parsed.path == "/healthz":
            self._send_json({"status": "ok", "db_path": str(self.server.db_path)})
            return
        if parsed.path == "/login":
            self._send_html(LOGIN_PAGE.replace("__ERROR_BLOCK__", ""))
            return
        if parsed.path == "/logout":
            token = self._session_token()
            delete_web_session(self.server.db_path, token)
            self._redirect("/login", headers={"Set-Cookie": "team_session=deleted; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
            return
        if parsed.path == "/dashboard":
            if not self._require_admin_page():
                return
            self._send_html(DASHBOARD_PAGE)
            return
        if parsed.path == "/api/me":
            admin = self._require_admin_json()
            if not admin:
                return
            self._send_json({"username": admin["username"], "teams": list_teams(self.server.db_path)})
            return
        if parsed.path == "/api/dashboard":
            admin = self._require_admin_json()
            if not admin:
                return
            query = parse_qs(parsed.query)
            team_id = (query.get("team_id") or [""])[0]
            teams = list_teams(self.server.db_path)
            if not team_id and teams:
                team_id = teams[0]
            if not team_id:
                self._send_json(
                    {
                        "team_id": "",
                        "summary": {"events": 0, "users": 0, "machines": 0, "projects": 0, "sessions": 0, "sources": 0, "total_tokens": 0, "cached_input_tokens": 0, "effective_tokens": 0},
                        "by_user": [],
                        "by_machine": [],
                        "by_project": [],
                        "by_model": [],
                        "by_source": [],
                        "trend": [],
                        "recent_events": [],
                        "agents": [],
                        "available_teams": [],
                        "window": {"label": "empty", "start": None, "end": None, "timezone": "Asia/Shanghai"},
                    }
                )
                return
            range_name = (query.get("range") or ["7d"])[0]
            limit = int((query.get("limit") or ["8"])[0])
            if range_name == "today":
                window = build_time_window(today=True, last=None, start=None, end=None, tz_name="Asia/Shanghai")
            elif range_name in {"7d", "30d"}:
                window = build_time_window(today=False, last=range_name, start=None, end=None, tz_name="Asia/Shanghai", default_mode=f"last:{range_name}")
            else:
                start = (query.get("start") or [None])[0]
                end = (query.get("end") or [None])[0]
                window = build_time_window(today=False, last=None, start=start, end=end, tz_name="Asia/Shanghai", default_mode="all")
            self._send_json(build_dashboard_payload(self.server.db_path, team_id=team_id, window=window, limit=limit))
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/login":
            form = self._read_form_body()
            username = form.get("username", "").strip()
            password = form.get("password", "")
            admin = authenticate_admin_user(self.server.db_path, username, password)
            if not admin:
                error_block = '<div class="error">用户名或密码错误。</div>'
                self._send_html(LOGIN_PAGE.replace("__ERROR_BLOCK__", error_block), status=401)
                return
            token = create_web_session(self.server.db_path, int(admin["id"]))
            self._redirect(
                "/dashboard",
                headers={"Set-Cookie": f"team_session={token}; Path=/; HttpOnly; SameSite=Lax"},
            )
            return

        if parsed.path == "/api/ingest":
            agent_token = self.headers.get("X-Agent-Token", "").strip()
            agent_row = authenticate_agent_token(self.server.db_path, agent_token)
            if not agent_row:
                self._send_json({"error": "invalid agent token"}, status=401)
                return
            body = self._read_json_body()
            events = body.get("events", []) if isinstance(body, dict) else []
            if not isinstance(events, list):
                self._send_json({"error": "events must be a list"}, status=400)
                return
            try:
                result = ingest_events(self.server.db_path, agent_row, events)
            except KeyError as exc:
                self._send_json({"error": f"missing field: {exc}"}, status=400)
                return
            self._send_json(
                {
                    **result,
                    "team_id": agent_row["team_id"],
                    "user_id": agent_row["user_id"],
                    "machine_id": agent_row["machine_id"],
                }
            )
            return

        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def create_server(db_path: Path, host: str, port: int) -> TeamHTTPServer:
    init_database(db_path)
    return TeamHTTPServer((host, port), TeamRequestHandler, db_path=db_path)


def command_init_db(args) -> int:
    init_database(args.db_path)
    print(json.dumps({"db_path": str(args.db_path), "initialized": True}, ensure_ascii=False, indent=2))
    return 0


def command_create_admin(args) -> int:
    init_database(args.db_path)
    payload = create_admin_user(args.db_path, args.username, args.password)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_issue_agent_token(args) -> int:
    init_database(args.db_path)
    payload = issue_agent_token(
        args.db_path,
        team_id=args.team_id,
        user_id=args.user_id,
        machine_id=args.machine_id,
        machine_label=args.machine_label,
        note=args.note,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_seed_sample(args) -> int:
    init_database(args.db_path)
    sample_path = Path(args.sample_file).expanduser()
    events = []
    with sample_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if raw_line:
                events.append(json.loads(raw_line))
    raw = issue_agent_token(
        args.db_path,
        team_id=args.team_id,
        user_id=args.user_id,
        machine_id=args.machine_id,
        machine_label=args.machine_label,
        note="seed-sample",
    )
    agent_row = authenticate_agent_token(args.db_path, raw["token"])
    assert agent_row is not None
    result = ingest_events(args.db_path, agent_row, events)
    print(json.dumps({"seeded": result, "token": raw["token"]}, ensure_ascii=False, indent=2))
    return 0


def command_run_server(args) -> int:
    init_database(args.db_path)
    server = create_server(args.db_path, args.host, args.port)
    host, port = server.server_address
    print(f"Team backend listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Token Usage Universal Team Backend")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="initialize SQLite database")
    init_db.set_defaults(func=command_init_db)

    create_admin = subparsers.add_parser("create-admin", help="create local admin account")
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--password", required=True)
    create_admin.set_defaults(func=command_create_admin)

    issue_token = subparsers.add_parser("issue-agent-token", help="create one device ingest token")
    issue_token.add_argument("--team-id", required=True)
    issue_token.add_argument("--user-id", required=True)
    issue_token.add_argument("--machine-id", required=True)
    issue_token.add_argument("--machine-label")
    issue_token.add_argument("--note")
    issue_token.set_defaults(func=command_issue_agent_token)

    seed_sample = subparsers.add_parser("seed-sample", help="seed DB with sample team JSONL")
    seed_sample.add_argument("--sample-file", default=str(Path(__file__).resolve().parents[1] / "examples" / "team-usage.sample.jsonl"))
    seed_sample.add_argument("--team-id", default="demo-team")
    seed_sample.add_argument("--user-id", default="seed-user")
    seed_sample.add_argument("--machine-id", default="seed-machine")
    seed_sample.add_argument("--machine-label", default="Seed Machine")
    seed_sample.set_defaults(func=command_seed_sample)

    run_server = subparsers.add_parser("run-server", help="run the intranet web backend")
    run_server.add_argument("--host", default="0.0.0.0")
    run_server.add_argument("--port", type=int, default=8787)
    run_server.set_defaults(func=command_run_server)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
