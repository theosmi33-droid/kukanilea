import argparse
import sqlite3
import time
from pathlib import Path


def run_check(db_path, action="quick_check"):
    conn = sqlite3.connect(db_path)
    start_time = time.time()
    try:
        cursor = conn.execute(f"PRAGMA {action};")
        rows = cursor.fetchall()
        duration = time.time() - start_time
        conn.close()
        return rows, duration
    except Exception as e:
        return [(str(e),)], time.time() - start_time

def run_vacuum(db_path):
    conn = sqlite3.connect(db_path)
    start_time = time.time()
    try:
        conn.execute("VACUUM;")
        conn.commit()
        duration = time.time() - start_time
        conn.close()
        return True, duration
    except Exception as e:
        return str(e), time.time() - start_time

def main():
    parser = argparse.ArgumentParser(description="KUKANILEA DB Maintenance")
    parser.add_argument("--db", required=True, help="Database path")
    parser.add_argument("--action", choices=["quick_check", "integrity_check", "vacuum"], required=True)
    parser.add_argument("--out", default="evidence/db", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "REPORT_DB_MAINTENANCE.md"
    
    rows, dur = [], 0.0
    if args.action in ["quick_check", "integrity_check"]:
        rows, dur = run_check(args.db, args.action)
        result_str = "\n".join([str(r[0]) for r in rows])
    elif args.action == "vacuum":
        success, dur = run_vacuum(args.db)
        result_str = "VACUUM completed" if success is True else f"FAILED: {success}"

    with open(report_path, "a") as f:
        f.write(f"\n## {args.action.upper()} - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- DB: {args.db}\n")
        f.write(f"- Duration: {dur:.4f}s\n")
        f.write(f"- Result:\n```\n{result_str}\n```\n")

    print(f"Maintenance {args.action} done. Evidence: {report_path}")

if __name__ == "__main__":
    main()
