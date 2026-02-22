import sqlite3
import time
import os
import json
from pathlib import Path

DB_PATH = Path("instance/benchmark.db")

def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Applying KUKANILEA Performance Defaults
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("CREATE TABLE perf_test (id INTEGER PRIMARY KEY, val TEXT);")
    conn.commit()
    return conn

def run_benchmark(conn, iterations=1000):
    print(f"Running SQLite benchmark ({iterations} iterations)...")
    
    start_time = time.perf_counter()
    
    for i in range(iterations):
        conn.execute("INSERT INTO perf_test (val) VALUES (?);", (f"test_{i}",))
        conn.commit()
        
    end_time = time.perf_counter()
    
    total_duration = (end_time - start_time) * 1000 # ms
    avg_latency = total_duration / iterations
    
    print(f"Total duration: {total_duration:.2f} ms")
    print(f"Average write latency: {avg_latency:.4f} ms")
    
    return {
        "iterations": iterations,
        "total_duration_ms": total_duration,
        "avg_latency_ms": avg_latency,
        "wal_mode": True,
        "synchronous": "NORMAL"
    }

def main():
    conn = setup_db()
    results = run_benchmark(conn)
    
    output_dir = Path("output/benchmarks")
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = int(time.time())
    output_path = output_dir / f"db_perf_{timestamp}.json"
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"Benchmark report saved to {output_path}")
    
    if results["avg_latency_ms"] < 1.0:
        print("[PASS] SQLite performance target met (< 1ms avg).")
    else:
        print("[FAIL] SQLite performance below target.")

if __name__ == "__main__":
    main()
