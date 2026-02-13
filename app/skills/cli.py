from __future__ import annotations

import argparse
import json
import sys

from app.skills.cache import write_cache
from app.skills.fetcher import fetch_skill_github
from app.skills.registry import (
    activate_skill,
    list_skills,
    quarantine_skill,
    register_skill,
)
from app.skills.util import sanitize_skill_name, utcnow_iso


def _cmd_add(args: argparse.Namespace) -> int:
    skill_name = sanitize_skill_name(args.skill)
    import_result = fetch_skill_github(args.repo_url, skill_name, ref=args.ref)
    cache_key, folder, manifest = write_cache(import_result)
    skill_id = register_skill(
        cache_key=cache_key,
        name=import_result.name,
        source_url=import_result.source_url,
        ref=import_result.ref,
        resolved_commit=import_result.resolved_commit,
        fetched_at_utc=manifest["meta"].get("fetched_at_utc", utcnow_iso()),
        manifest_dict=manifest,
        status="quarantine",
        actor_user_id=args.actor_user_id,
    )
    print(
        json.dumps(
            {
                "skill_id": skill_id,
                "cache_key": cache_key,
                "status": "quarantine",
                "folder": str(folder),
            },
            sort_keys=True,
        )
    )
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    del args
    items = list_skills()
    print("id\tcache_key\tname\tstatus\tfetched_at")
    for row in items:
        print(
            f"{row.get('id')}\t{row.get('cache_key')}\t{row.get('name')}"
            f"\t{row.get('status')}\t{row.get('fetched_at')}"
        )
    return 0


def _cmd_activate(args: argparse.Namespace) -> int:
    pointer = activate_skill(int(args.skill_id), actor_user_id=args.actor_user_id)
    print(json.dumps(pointer, sort_keys=True))
    return 0


def _cmd_quarantine(args: argparse.Namespace) -> int:
    quarantine_skill(int(args.skill_id), actor_user_id=args.actor_user_id)
    print(
        json.dumps(
            {"skill_id": int(args.skill_id), "status": "quarantine"}, sort_keys=True
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.skills.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("repo_url")
    add.add_argument("--skill", required=True)
    add.add_argument("--ref", default="main")
    add.add_argument("--actor-user-id", type=int, default=None)
    add.set_defaults(func=_cmd_add)

    ls = sub.add_parser("list")
    ls.set_defaults(func=_cmd_list)

    act = sub.add_parser("activate")
    act.add_argument("skill_id", type=int)
    act.add_argument("--actor-user-id", type=int, default=None)
    act.set_defaults(func=_cmd_activate)

    qua = sub.add_parser("quarantine")
    qua.add_argument("skill_id", type=int)
    qua.add_argument("--actor-user-id", type=int, default=None)
    qua.set_defaults(func=_cmd_quarantine)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
