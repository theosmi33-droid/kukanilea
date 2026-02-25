import argparse
import sqlite3
import time
from pathlib import Path


def run_check(db_path, deep=False):
    conn = sqlite3.connect(db_path)
    pragma = "integrity_check" if deep else "quick_check"
    start_time = time.time()
    try:
        cursor = conn.execute(f"PRAGMA {pragma};")
        result = cursor.fetchall()
        duration = time.time() - start_time
        conn.close()
        return result, duration
    except Exception as e:
        return [str(e)], time.time() - start_time

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

def run_wal_checkpoint(db_path):
    conn = sqlite3.connect(db_path)
    start_time = time.time()
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL);")
        duration = time.time() - start_time
        conn.close()
        return True, duration
    except Exception as e:
        return str(e), time.time() - start_time

def main():
    parser = argparse.ArgumentParser(description="SQLite Maintenance tool")
    parser.add_argument("--db", required=True, help="Database path")
    parser.add_argument("--quick-check", action="store_true", help="Run PRAGMA quick_check")
    parser.add_argument("--integrity-check", action="store_true", help="Run PRAGMA integrity_check")
    parser.add_argument("--vacuum", action="store_true", help="Run VACUUM")
    parser.add_argument("--wal-checkpoint", action="store_true", help="Run PRAGMA wal_checkpoint(FULL)")
    parser.add_argument("--out", default="evidence/db", help="Output directory for reports")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "REPORT_DB_MAINTENANCE.md"
    
    with open(report_path, "a") as f:
        f.write(f"\n## Maintenance Session: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- DB: {args.db}\n")

        if args.quick_check:
            res, dur = run_check(args.db, deep=False)
            f.write(f"- Quick Check: {res} ({dur:.4f}s)\n")
            print(f"Quick Check: {res}")

        if args.integrity_check:
            res, dur = run_check(args.db, deep=True)
            f.write(f"- Integrity Check: {res} ({dur:.4f}s)\n")
            print(f"Integrity Check: {res}")

        if args.vacuum:
            res, dur = run_vacuum(args.db)
            f.write(f"- Vacuum: {'Success' if res is True else res} ({dur:.4f}s)\n")
            print(f"Vacuum: {res}")

        if args.wal_checkpoint:
            res, dur = run_wal_checkpoint(args.db)
            f.write(f"- WAL Checkpoint: {'Success' if res is True else res} ({dur:.4f}s)\n")
            print(f"WAL Checkpoint: {res}")

    print(f"Maintenance complete. Evidence appended to {report_path}")

if __name__ == "__main__":
    main()
