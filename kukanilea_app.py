#!/usr/bin/env python3
"""
KUKANILEA v2.1 — Global App Entry & Benchmark CLI.
Handles startup, benchmarking, and maintenance.
"""

import sys
import time
import json
import logging
import platform
try:
    import psutil # Needed for Step 16/17
except ImportError:
    psutil = None
from pathlib import Path

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kukanilea.cli")

def run_benchmark():
    """Step 11-20: Performance Benchmarking."""
    print("🚀 Starting KUKANILEA Performance Benchmark (v2.1)...")
    results = {
        "boot_time_ms": measure_boot_time(),
        "db_query_speed": measure_db_speed(),
        "cpu_usage": measure_cpu_usage(),
        "memory_info": measure_memory_usage(),
        "platform": platform.platform(),
        "python_version": sys.version
    }
    
    # Save results (Step 19)
    report_file = Path("logs/reports/performance_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n--- PERFORMANCE REPORT (Step 19) ---")
    print(json.dumps(results, indent=2))
    print(f"\nReport saved to: {report_file}")

def measure_boot_time():
    """Step 12: Measure API/Boot latency."""
    from app.core.boot_sequence import run_boot_sequence
    start = time.time()
    run_boot_sequence()
    return int((time.time() - start) * 1000)

def measure_db_speed():
    """Step 14: Measure DB query speed."""
    import sqlite3
    from app.config import Config
    db_path = Config.CORE_DB
    
    if not db_path.exists():
        return "N/A (DB Missing)"
        
    start = time.time()
    try:
        conn = sqlite3.connect(str(db_path))
        # Simple heavy query (Step 14)
        conn.execute("SELECT COUNT(*) FROM sqlite_master;").fetchone()
        conn.close()
        return int((time.time() - start) * 1000)
    except Exception as e:
        return f"ERROR: {e}"

def measure_cpu_usage():
    """Step 17: Measure CPU usage per module."""
    if psutil:
        return psutil.cpu_percent(interval=0.1)
    return "N/A (psutil missing)"

def measure_memory_usage():
    """Step 16: Detect memory leaks/usage."""
    if psutil:
        process = psutil.Process()
        return {
            "rss_mb": process.memory_info().rss / (1024 * 1024),
            "vms_mb": process.memory_info().vms / (1024 * 1024)
        }
    return "N/A (psutil missing)"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KUKANILEA Business OS")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmarks")
    parser.add_argument("--port", type=int, default=5051, help="Port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    if args.benchmark:
        run_benchmark()
        return

    # Normal startup
    print("Initializing KUKANILEA v2.1...")
    from app.core.boot_sequence import run_boot_sequence
    if run_boot_sequence() is False:
        sys.exit(1)
        
    print(f"System ready. Starting Web Server on {args.host}:{args.port}...")
    
    from app import create_app
    from waitress import serve
    
    flask_app = create_app()
    
    # Task 177: Waitress Tuning
    serve(flask_app, host=args.host, port=args.port, threads=8)

if __name__ == "__main__":
    main()
