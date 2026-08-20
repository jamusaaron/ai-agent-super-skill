#!/usr/bin/env python3
# Agent memory store: conversations, tool results, learned facts
#
# Faithful extract of the CGI-bin backend from SKILL.md (section 10.1).
# It speaks the CGI protocol: request details come from environment variables
# (REQUEST_METHOD, PATH_INFO, QUERY_STRING) and the JSON body from stdin.
#
# Example (create a session):
#   REQUEST_METHOD=POST PATH_INFO=/sessions \
#     python3 examples/agent_memory_cgi.py <<< '{"metadata": {"user": "demo"}}'

import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.environ.get("AGENT_MEMORY_DB", "agent_memory.db")


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata    TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('user','assistant','tool','system')),
            content     TEXT NOT NULL,
            tool_name   TEXT,
            tool_input  TEXT,
            tool_result TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS facts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            confidence  REAL DEFAULT 1.0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at  TIMESTAMP,
            UNIQUE(session_id, key)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
    """)
    conn.commit()


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
init_db(conn)

method = os.environ.get("REQUEST_METHOD", "GET")
query = os.environ.get("QUERY_STRING", "")
path_info = os.environ.get("PATH_INFO", "")


def respond(data, status=200):
    print(f"Status: {status}")
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))


def parse_qs(qs):
    params = {}
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return params


# -- Routes --------------------------------------------------------------------
if path_info == "/sessions" and method == "POST":
    body = json.loads(sys.stdin.read() or "{}")
    sid = body.get("session_id") or f"sess_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    conn.execute("INSERT OR IGNORE INTO sessions (session_id, metadata) VALUES (?,?)",
                 [sid, json.dumps(body.get("metadata", {}))])
    conn.commit()
    respond({"session_id": sid}, 201)

elif path_info == "/messages" and method == "POST":
    body = json.loads(sys.stdin.read())
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, tool_input, tool_result) "
        "VALUES (?,?,?,?,?,?)",
        [body["session_id"], body["role"], body["content"],
         body.get("tool_name"), body.get("tool_input"), body.get("tool_result")]
    )
    conn.commit()
    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    respond({"id": msg_id}, 201)

elif path_info == "/messages" and method == "GET":
    params = parse_qs(query)
    sid = params.get("session_id", "")
    limit = int(params.get("limit", 50))
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id=? ORDER BY created_at LIMIT ?",
        [sid, limit]
    ).fetchall()
    respond([dict(r) for r in rows])

elif path_info == "/facts" and method == "PUT":
    body = json.loads(sys.stdin.read())
    conn.execute(
        "INSERT OR REPLACE INTO facts (session_id, key, value, confidence) VALUES (?,?,?,?)",
        [body.get("session_id"), body["key"], json.dumps(body["value"]),
         body.get("confidence", 1.0)]
    )
    conn.commit()
    respond({"status": "ok"})

elif path_info == "/facts" and method == "GET":
    params = parse_qs(query)
    sid = params.get("session_id", "")
    rows = conn.execute(
        "SELECT key, value, confidence FROM facts WHERE session_id=? OR session_id IS NULL",
        [sid]
    ).fetchall()
    respond({r["key"]: {"value": json.loads(r["value"]), "confidence": r["confidence"]}
             for r in rows})

else:
    respond({"error": f"Unknown route: {method} {path_info}"}, 400)
