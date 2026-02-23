import subprocess
import sys


def test_benchmark_smoke(tmp_path):
    db_path = tmp_path / "smoke.db"
    out_dir = tmp_path / "evidence"
    
    # Run benchmark script
    res = subprocess.run([
        sys.executable, "scripts/benchmark_db.py",
        "--db", str(db_path),
        "--rows", "10",
        "--out", str(out_dir)
    ], capture_output=True, text=True)
    
    assert res.returncode == 0
    assert (out_dir / "REPORT_DB_BENCHMARK.md").exists()
    assert (out_dir / "db_bench.csv").exists()
    
    report_content = (out_dir / "REPORT_DB_BENCHMARK.md").read_text()
    assert "SQLite DB Benchmark Report" in report_content
    assert "Compliance Note" in report_content
    assert "lose durability" in report_content.lower()
