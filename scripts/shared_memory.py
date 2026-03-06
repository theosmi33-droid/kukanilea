#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path('/Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db')


@dataclass
class SharedMemory:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA journal_mode=WAL;')
        con.execute('PRAGMA synchronous=NORMAL;')
        con.execute('PRAGMA busy_timeout=8000;')
        return con

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS global_context (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_by TEXT DEFAULT 'unknown',
                    updated_at TEXT NOT NULL
                )
                '''
            )
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS domain_sync (
                    domain TEXT PRIMARY KEY,
                    last_action TEXT,
                    last_commit TEXT,
                    status TEXT,
                    updated_by TEXT DEFAULT 'unknown',
                    source TEXT DEFAULT 'unknown',
                    updated_at TEXT NOT NULL
                )
                '''
            )
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS shared_directives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    directive TEXT,
                    active INTEGER DEFAULT 1,
                    created_by TEXT DEFAULT 'unknown',
                    created_at TEXT NOT NULL,
                    deactivated_at TEXT
                )
                '''
            )
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS sync_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                '''
            )
            con.execute('CREATE INDEX IF NOT EXISTS idx_sync_events_domain_ts ON sync_events(domain, ts_utc DESC)')
            con.execute('CREATE INDEX IF NOT EXISTS idx_shared_directives_active ON shared_directives(active, created_at DESC)')

            self._ensure_column(con, 'global_context', 'updated_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'domain_sync', 'updated_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'domain_sync', 'source', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'shared_directives', 'created_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'shared_directives', 'deactivated_at', 'TEXT')

            now = _utc_iso()
            con.execute(
                '''
                INSERT INTO global_context(key, value, updated_by, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                ''',
                ('system_state', 'FLEET_COMMANDER_ACTIVE', 'system', now),
            )

    def _ensure_column(self, con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {r['name'] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
        if column not in cols:
            con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')

    def set_context(self, key: str, value: str, actor: str, source: str) -> None:
        now = _utc_iso()
        with self.connect() as con:
            con.execute(
                '''
                INSERT INTO global_context(key, value, updated_by, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at
                ''',
                (key, value, actor, now),
            )
            self._event(con, actor, source, 'global', 'context_set', {'key': key, 'value': value})

    def upsert_domain(self, domain: str, action: str, commit: str, status: str, actor: str, source: str) -> None:
        now = _utc_iso()
        with self.connect() as con:
            con.execute(
                '''
                INSERT INTO domain_sync(domain, last_action, last_commit, status, updated_by, source, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    last_action=excluded.last_action,
                    last_commit=excluded.last_commit,
                    status=excluded.status,
                    updated_by=excluded.updated_by,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                ''',
                (domain, action, commit, status, actor, source, now),
            )
            self._event(con, actor, source, domain, 'domain_sync', {
                'last_action': action,
                'last_commit': commit,
                'status': status,
            })

    def add_directive(self, directive: str, actor: str, source: str) -> int:
        now = _utc_iso()
        with self.connect() as con:
            cur = con.execute(
                '''
                INSERT INTO shared_directives(directive, active, created_by, created_at)
                VALUES(?, 1, ?, ?)
                ''',
                (directive, actor, now),
            )
            directive_id = int(cur.lastrowid)
            self._event(con, actor, source, 'global', 'directive_add', {'id': directive_id, 'directive': directive})
            return directive_id

    def deactivate_directive(self, directive_id: int, actor: str, source: str) -> None:
        now = _utc_iso()
        with self.connect() as con:
            con.execute(
                '''
                UPDATE shared_directives
                SET active=0, deactivated_at=?
                WHERE id=?
                ''',
                (now, directive_id),
            )
            self._event(con, actor, source, 'global', 'directive_deactivate', {'id': directive_id})

    def read_state(self) -> dict[str, Any]:
        with self.connect() as con:
            gc = [dict(r) for r in con.execute('SELECT key, value, updated_by, updated_at FROM global_context ORDER BY key').fetchall()]
            ds = [dict(r) for r in con.execute('SELECT domain, last_action, last_commit, status, updated_by, source, updated_at FROM domain_sync ORDER BY updated_at DESC').fetchall()]
            sd = [dict(r) for r in con.execute('SELECT id, directive, active, created_by, created_at, deactivated_at FROM shared_directives WHERE active=1 ORDER BY created_at DESC').fetchall()]
            recent = [dict(r) for r in con.execute('SELECT id, ts_utc, actor, source, domain, event_type, payload_json FROM sync_events ORDER BY id DESC LIMIT 50').fetchall()]
            return {
                'db_path': str(self.db_path),
                'global_context': gc,
                'domain_sync': ds,
                'active_directives': sd,
                'recent_events': recent,
            }

    def snapshot(self, output: Path) -> Path:
        state = self.read_state()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(state, ensure_ascii=True, indent=2) + '\n')
        return output

    def _event(
        self,
        con: sqlite3.Connection,
        actor: str,
        source: str,
        domain: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        con.execute(
            '''
            INSERT INTO sync_events(ts_utc, actor, source, domain, event_type, payload_json)
            VALUES(?, ?, ?, ?, ?, ?)
            ''',
            (_utc_iso(), actor, source, domain, event_type, json.dumps(payload, ensure_ascii=True, sort_keys=True)),
        )


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Shared memory CLI for KUKANILEA multi-agent sync.')
    p.add_argument('--db', type=Path, default=DEFAULT_DB, help='Path to shared sqlite db')

    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('init', help='Initialize/upgrade schema idempotently')
    sub.add_parser('read', help='Read current shared state as JSON')

    c = sub.add_parser('set-context', help='Set a global context key/value')
    c.add_argument('--key', required=True)
    c.add_argument('--value', required=True)
    c.add_argument('--actor', required=True)
    c.add_argument('--source', required=True)

    d = sub.add_parser('upsert-domain', help='Upsert domain sync state')
    d.add_argument('--domain', required=True)
    d.add_argument('--action', required=True)
    d.add_argument('--commit', required=True)
    d.add_argument('--status', required=True)
    d.add_argument('--actor', required=True)
    d.add_argument('--source', required=True)

    a = sub.add_parser('add-directive', help='Add active shared directive')
    a.add_argument('--directive', required=True)
    a.add_argument('--actor', required=True)
    a.add_argument('--source', required=True)

    dd = sub.add_parser('deactivate-directive', help='Deactivate shared directive by id')
    dd.add_argument('--id', type=int, required=True)
    dd.add_argument('--actor', required=True)
    dd.add_argument('--source', required=True)

    s = sub.add_parser('snapshot', help='Write JSON snapshot for local diagnostics')
    s.add_argument('--output', type=Path, default=Path('instance/shared_memory_snapshot.json'))

    return p


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    sm = SharedMemory(db_path=args.db)

    if args.cmd == 'init':
        sm.init()
        print(json.dumps({'ok': True, 'action': 'init', 'db': str(args.db)}))
        return 0

    if args.cmd == 'read':
        print(json.dumps(sm.read_state(), ensure_ascii=True, indent=2))
        return 0

    if args.cmd == 'set-context':
        sm.init()
        sm.set_context(args.key, args.value, args.actor, args.source)
        print(json.dumps({'ok': True, 'action': 'set-context', 'key': args.key}))
        return 0

    if args.cmd == 'upsert-domain':
        sm.init()
        sm.upsert_domain(args.domain, args.action, args.commit, args.status, args.actor, args.source)
        print(json.dumps({'ok': True, 'action': 'upsert-domain', 'domain': args.domain}))
        return 0

    if args.cmd == 'add-directive':
        sm.init()
        directive_id = sm.add_directive(args.directive, args.actor, args.source)
        print(json.dumps({'ok': True, 'action': 'add-directive', 'id': directive_id}))
        return 0

    if args.cmd == 'deactivate-directive':
        sm.init()
        sm.deactivate_directive(args.id, args.actor, args.source)
        print(json.dumps({'ok': True, 'action': 'deactivate-directive', 'id': args.id}))
        return 0

    if args.cmd == 'snapshot':
        sm.init()
        out = sm.snapshot(args.output)
        print(json.dumps({'ok': True, 'action': 'snapshot', 'output': str(out)}))
        return 0

    parser.print_help()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
