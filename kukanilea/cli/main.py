from __future__ import annotations

import argparse

from kukanilea.config import doctor_report, load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="kukanilea")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("seed-users")
    sub.add_parser("ingest")
    sub.add_parser("reindex")
    sub.add_parser("doctor")
    args = parser.parse_args()

    if args.cmd == "doctor":
        print(doctor_report())
        return
    if args.cmd == "serve":
        config = load_config()
        print(f"Serve not wired yet; secret={config.secret_key[:4]}***")
        return
    print(f"{args.cmd} not implemented yet")


if __name__ == "__main__":
    main()
