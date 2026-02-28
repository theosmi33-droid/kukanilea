from __future__ import annotations

import argparse
from datetime import datetime

from app.auth import hash_password
from app.config import Config
from app.db import AuthDB


def _now() -> str:
    return datetime.utcnow().isoformat()


def cmd_reset_password(args: argparse.Namespace) -> int:
    db = AuthDB(Config.AUTH_DB)
    db.init()
    user = db.get_user(args.username)
    if not user and not args.create_if_missing:
        print(f"[ERROR] user_not_found: {args.username}")
        return 2

    if not user and args.create_if_missing:
        db.upsert_user(args.username, hash_password(args.password), _now())
        db.upsert_tenant(args.tenant, args.tenant, _now())
        db.upsert_membership(args.username, args.tenant, args.role, _now())
        print(f"[OK] created user={args.username} tenant={args.tenant} role={args.role}")
        return 0

    db.upsert_user(args.username, hash_password(args.password), _now())
    print(f"[OK] password_reset user={args.username}")
    return 0


def cmd_ensure_user(args: argparse.Namespace) -> int:
    db = AuthDB(Config.AUTH_DB)
    db.init()
    db.upsert_tenant(args.tenant, args.tenant, _now())
    db.upsert_user(args.username, hash_password(args.password), _now())
    db.upsert_membership(args.username, args.tenant, args.role, _now())
    print(f"[OK] ensured user={args.username} tenant={args.tenant} role={args.role}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="KUKANILEA auth break-glass")
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("reset-password", help="reset password for existing user")
    rp.add_argument("--username", required=True)
    rp.add_argument("--password", required=True)
    rp.add_argument("--create-if-missing", action="store_true")
    rp.add_argument("--tenant", default="KUKANILEA")
    rp.add_argument("--role", default="DEV")
    rp.set_defaults(func=cmd_reset_password)

    eu = sub.add_parser("ensure-user", help="create or update user+membership")
    eu.add_argument("--username", required=True)
    eu.add_argument("--password", required=True)
    eu.add_argument("--tenant", default="KUKANILEA")
    eu.add_argument("--role", default="DEV")
    eu.set_defaults(func=cmd_ensure_user)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
