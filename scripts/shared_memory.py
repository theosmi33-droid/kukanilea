#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    branch TEXT,
                    worktree TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    note TEXT,
                    started_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    ended_at TEXT
                )
                '''
            )
            con.execute(
                '''
                CREATE TABLE IF NOT EXISTS domain_locks (
                    domain TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reason TEXT,
                    locked_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                '''
            )

            con.execute('CREATE INDEX IF NOT EXISTS idx_sync_events_domain_ts ON sync_events(domain, ts_utc DESC)')
            con.execute('CREATE INDEX IF NOT EXISTS idx_shared_directives_active ON shared_directives(active, created_at DESC)')
            con.execute('CREATE INDEX IF NOT EXISTS idx_agent_sessions_domain_status ON agent_sessions(domain, status, heartbeat_at DESC)')
            con.execute('CREATE INDEX IF NOT EXISTS idx_domain_locks_expires ON domain_locks(expires_at)')

            self._ensure_column(con, 'global_context', 'updated_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'domain_sync', 'updated_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'domain_sync', 'source', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'shared_directives', 'created_by', "TEXT DEFAULT 'unknown'")
            self._ensure_column(con, 'shared_directives', 'deactivated_at', 'TEXT')
            self._ensure_column(con, 'agent_sessions', 'note', 'TEXT')
            self._ensure_column(con, 'agent_sessions', 'ended_at', 'TEXT')
            self._ensure_column(con, 'domain_locks', 'reason', 'TEXT')

            self._purge_expired_locks(con)

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

    def _purge_expired_locks(self, con: sqlite3.Connection) -> None:
        now = _utc_iso()
        con.execute('DELETE FROM domain_locks WHERE expires_at <= ?', (now,))

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
            self._event(
                con,
                actor,
                source,
                domain,
                'domain_sync',
                {
                    'last_action': action,
                    'last_commit': commit,
                    'status': status,
                },
            )

    def seed_domains(self, domains: list[str], actor: str, source: str, status: str = 'PENDING') -> int:
        now = _utc_iso()
        inserted = 0
        with self.connect() as con:
            for domain in domains:
                cur = con.execute(
                    '''
                    INSERT OR IGNORE INTO domain_sync(domain, last_action, last_commit, status, updated_by, source, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (domain, 'seeded_by_fleet', 'none', status, actor, source, now),
                )
                if cur.rowcount:
                    inserted += 1
                    self._event(
                        con,
                        actor,
                        source,
                        domain,
                        'domain_seed',
                        {'status': status},
                    )
        return inserted

    def start_session(
        self,
        actor: str,
        source: str,
        domain: str,
        branch: str,
        worktree: str,
        note: str,
        session_id: str | None = None,
    ) -> str:
        now = _utc_iso()
        sid = session_id or f'{source}:{actor}:{domain}:{uuid.uuid4().hex[:8]}'
        with self.connect() as con:
            con.execute(
                '''
                INSERT INTO agent_sessions(session_id, actor, source, domain, branch, worktree, status, note, started_at, heartbeat_at, ended_at)
                VALUES(?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, NULL)
                ON CONFLICT(session_id) DO UPDATE SET
                    actor=excluded.actor,
                    source=excluded.source,
                    domain=excluded.domain,
                    branch=excluded.branch,
                    worktree=excluded.worktree,
                    status='ACTIVE',
                    note=excluded.note,
                    heartbeat_at=excluded.heartbeat_at,
                    ended_at=NULL
                ''',
                (sid, actor, source, domain, branch, worktree, note, now, now),
            )
            self._event(
                con,
                actor,
                source,
                domain,
                'session_start',
                {'session_id': sid, 'branch': branch, 'worktree': worktree, 'note': note},
            )
        return sid

    def heartbeat(self, session_id: str, actor: str, source: str, status: str, note: str) -> bool:
        now = _utc_iso()
        with self.connect() as con:
            cur = con.execute(
                '''
                UPDATE agent_sessions
                SET heartbeat_at=?, status=?, note=?
                WHERE session_id=? AND ended_at IS NULL
                ''',
                (now, status, note, session_id),
            )
            if cur.rowcount == 0:
                return False
            row = con.execute('SELECT domain FROM agent_sessions WHERE session_id=?', (session_id,)).fetchone()
            domain = row['domain'] if row else 'global'
            self._event(
                con,
                actor,
                source,
                domain,
                'session_heartbeat',
                {'session_id': session_id, 'status': status, 'note': note},
            )
            return True

    def end_session(self, session_id: str, actor: str, source: str, status: str, note: str) -> bool:
        now = _utc_iso()
        with self.connect() as con:
            row = con.execute(
                'SELECT domain FROM agent_sessions WHERE session_id=? AND ended_at IS NULL',
                (session_id,),
            ).fetchone()
            if not row:
                return False
            con.execute(
                '''
                UPDATE agent_sessions
                SET status=?, note=?, heartbeat_at=?, ended_at=?
                WHERE session_id=?
                ''',
                (status, note, now, now, session_id),
            )
            self._event(
                con,
                actor,
                source,
                row['domain'],
                'session_end',
                {'session_id': session_id, 'status': status, 'note': note},
            )
            return True

    def lock_domain(
        self,
        domain: str,
        session_id: str,
        actor: str,
        source: str,
        minutes: int,
        reason: str,
    ) -> tuple[bool, dict[str, Any] | None]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        lock_until = now + timedelta(minutes=max(1, minutes))
        now_iso = now.isoformat().replace('+00:00', 'Z')
        until_iso = lock_until.isoformat().replace('+00:00', 'Z')
        with self.connect() as con:
            self._purge_expired_locks(con)
            current = con.execute('SELECT * FROM domain_locks WHERE domain=?', (domain,)).fetchone()
            if current and current['session_id'] != session_id:
                return False, dict(current)

            con.execute(
                '''
                INSERT INTO domain_locks(domain, session_id, actor, source, reason, locked_at, expires_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    session_id=excluded.session_id,
                    actor=excluded.actor,
                    source=excluded.source,
                    reason=excluded.reason,
                    locked_at=excluded.locked_at,
                    expires_at=excluded.expires_at
                ''',
                (domain, session_id, actor, source, reason, now_iso, until_iso),
            )
            self._event(
                con,
                actor,
                source,
                domain,
                'domain_lock',
                {'session_id': session_id, 'minutes': minutes, 'reason': reason, 'expires_at': until_iso},
            )
            return True, None

    def unlock_domain(self, domain: str, session_id: str, actor: str, source: str) -> bool:
        with self.connect() as con:
            cur = con.execute('DELETE FROM domain_locks WHERE domain=? AND session_id=?', (domain, session_id))
            if cur.rowcount == 0:
                return False
            self._event(
                con,
                actor,
                source,
                domain,
                'domain_unlock',
                {'session_id': session_id},
            )
            return True

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
            self._purge_expired_locks(con)
            gc = [
                dict(r)
                for r in con.execute('SELECT key, value, updated_by, updated_at FROM global_context ORDER BY key').fetchall()
            ]
            ds = [
                dict(r)
                for r in con.execute(
                    'SELECT domain, last_action, last_commit, status, updated_by, source, updated_at FROM domain_sync ORDER BY updated_at DESC'
                ).fetchall()
            ]
            sd = [
                dict(r)
                for r in con.execute(
                    'SELECT id, directive, active, created_by, created_at, deactivated_at FROM shared_directives WHERE active=1 ORDER BY created_at DESC'
                ).fetchall()
            ]
            locks = [
                dict(r)
                for r in con.execute(
                    '''
                    SELECT domain, session_id, actor, source, reason, locked_at, expires_at
                    FROM domain_locks
                    ORDER BY domain
                    '''
                ).fetchall()
            ]
            sessions = [
                dict(r)
                for r in con.execute(
                    '''
                    SELECT session_id, actor, source, domain, branch, worktree, status, note, started_at, heartbeat_at, ended_at
                    FROM agent_sessions
                    WHERE ended_at IS NULL
                    ORDER BY heartbeat_at DESC
                    '''
                ).fetchall()
            ]
            recent = [
                dict(r)
                for r in con.execute(
                    'SELECT id, ts_utc, actor, source, domain, event_type, payload_json FROM sync_events ORDER BY id DESC LIMIT 50'
                ).fetchall()
            ]
            return {
                'db_path': str(self.db_path),
                'global_context': gc,
                'domain_sync': ds,
                'active_directives': sd,
                'active_locks': locks,
                'active_sessions': sessions,
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

    ss = sub.add_parser('start-session', help='Start or refresh an active agent session')
    ss.add_argument('--actor', required=True)
    ss.add_argument('--source', required=True)
    ss.add_argument('--domain', required=True)
    ss.add_argument('--branch', default='unknown')
    ss.add_argument('--worktree', default='unknown')
    ss.add_argument('--note', default='')
    ss.add_argument('--session-id', default=None)

    hb = sub.add_parser('heartbeat', help='Heartbeat for active session')
    hb.add_argument('--session-id', required=True)
    hb.add_argument('--actor', required=True)
    hb.add_argument('--source', required=True)
    hb.add_argument('--status', default='ACTIVE')
    hb.add_argument('--note', default='')

    es = sub.add_parser('end-session', help='End active session')
    es.add_argument('--session-id', required=True)
    es.add_argument('--actor', required=True)
    es.add_argument('--source', required=True)
    es.add_argument('--status', default='COMPLETED')
    es.add_argument('--note', default='')

    ld = sub.add_parser('lock-domain', help='Acquire domain lock with TTL')
    ld.add_argument('--domain', required=True)
    ld.add_argument('--session-id', required=True)
    ld.add_argument('--actor', required=True)
    ld.add_argument('--source', required=True)
    ld.add_argument('--minutes', type=int, default=120)
    ld.add_argument('--reason', default='active_work')

    ud = sub.add_parser('unlock-domain', help='Release domain lock')
    ud.add_argument('--domain', required=True)
    ud.add_argument('--session-id', required=True)
    ud.add_argument('--actor', required=True)
    ud.add_argument('--source', required=True)

    se = sub.add_parser('seed-domains', help='Insert missing domains with default state')
    se.add_argument('--domains', required=True, help='Comma-separated domain ids')
    se.add_argument('--actor', required=True)
    se.add_argument('--source', required=True)
    se.add_argument('--status', default='PENDING')

    s = sub.add_parser('snapshot', help='Write JSON snapshot for git/docs')
    s.add_argument('--output', type=Path, default=Path('docs/shared_memory_snapshot.json'))

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

    if args.cmd == 'start-session':
        sm.init()
        sid = sm.start_session(
            actor=args.actor,
            source=args.source,
            domain=args.domain,
            branch=args.branch,
            worktree=args.worktree,
            note=args.note,
            session_id=args.session_id,
        )
        print(json.dumps({'ok': True, 'action': 'start-session', 'session_id': sid}))
        return 0

    if args.cmd == 'heartbeat':
        sm.init()
        ok = sm.heartbeat(args.session_id, args.actor, args.source, args.status, args.note)
        print(json.dumps({'ok': ok, 'action': 'heartbeat', 'session_id': args.session_id}))
        return 0 if ok else 3

    if args.cmd == 'end-session':
        sm.init()
        ok = sm.end_session(args.session_id, args.actor, args.source, args.status, args.note)
        print(json.dumps({'ok': ok, 'action': 'end-session', 'session_id': args.session_id}))
        return 0 if ok else 3

    if args.cmd == 'lock-domain':
        sm.init()
        ok, lock = sm.lock_domain(
            domain=args.domain,
            session_id=args.session_id,
            actor=args.actor,
            source=args.source,
            minutes=args.minutes,
            reason=args.reason,
        )
        out = {'ok': ok, 'action': 'lock-domain', 'domain': args.domain, 'session_id': args.session_id}
        if lock:
            out['blocking_lock'] = lock
        print(json.dumps(out))
        return 0 if ok else 3

    if args.cmd == 'unlock-domain':
        sm.init()
        ok = sm.unlock_domain(args.domain, args.session_id, args.actor, args.source)
        print(json.dumps({'ok': ok, 'action': 'unlock-domain', 'domain': args.domain, 'session_id': args.session_id}))
        return 0 if ok else 3

    if args.cmd == 'seed-domains':
        sm.init()
        domains = [x.strip() for x in args.domains.split(',') if x.strip()]
        inserted = sm.seed_domains(domains=domains, actor=args.actor, source=args.source, status=args.status)
        print(json.dumps({'ok': True, 'action': 'seed-domains', 'inserted': inserted, 'domains': domains}))
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
