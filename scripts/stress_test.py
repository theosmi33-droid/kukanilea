"""
scripts/stress_test.py
KUKANILEA v2.1 Stress Test Script.
Simulate concurrent users, tasks, and files (Step 21-30).
"""

import time
import uuid
import sqlite3
import random
from pathlib import Path
from typing import Dict, Any

class StressTester:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def run_stress_test(self, users: int = 10, tasks: int = 100, files: int = 100):
        """Step 22-25: Simulate load."""
        print(f"--- KUKANILEA v2.1 Stress Test START ---")
        start = time.time()
        
        try:
            self.simulate_users(users)
            self.simulate_tasks(tasks)
            self.simulate_files(files)
            
            elapsed = time.time() - start
            print(f"Stress test PASSED in {elapsed:.2f}s")
            self.create_report(users, tasks, files, elapsed)
            
        except Exception as e:
            print(f"Stress test FAILED: {e}")
            
    def simulate_users(self, count: int):
        """Step 61-70: User Management simulation."""
        con = sqlite3.connect(str(self.db_path))
        for i in range(count):
            u_id = str(uuid.uuid4())
            con.execute("INSERT OR IGNORE INTO users(username, password_hash, created_at) VALUES (?,?,?)",
                        (f"user_{i}", f"hash_{i}", time.ctime()))
        con.commit()
        con.close()
        print(f"Simulated {count} users (Step 22/61).")

    def simulate_tasks(self, count: int):
        """Step 71-85: Kanban tasks simulation."""
        con = sqlite3.connect(str(self.db_path))
        # Ensure a board exists
        b_id = str(uuid.uuid4())
        con.execute("INSERT OR IGNORE INTO projects(id, tenant_id, name, created_at) VALUES (?,?,?,?)", ("P1", "T1", "Project 1", time.ctime()))
        con.execute("INSERT OR IGNORE INTO boards(id, project_id, name, created_at) VALUES (?,?,?,?)", (b_id, "P1", "Board 1", time.ctime()))
        
        for i in range(count):
            t_id = str(uuid.uuid4())
            con.execute("INSERT INTO tasks(id, board_id, column_name, title, created_at) VALUES (?,?,?,?,?)",
                        (t_id, b_id, random.choice(["To Do", "Doing", "Done"]), f"Task {i}", time.ctime()))
        con.commit()
        con.close()
        print(f"Simulated {count} tasks (Step 23/74).")

    def simulate_files(self, count: int):
        """Step 86-95: File management simulation."""
        con = sqlite3.connect(str(self.db_path))
        for i in range(count):
            f_id = str(uuid.uuid4())
            con.execute("INSERT INTO files(id, tenant_id, name, path, size, created_at) VALUES (?,?,?,?,?,?)",
                        (f_id, "T1", f"file_{i}.txt", f"/fake/path/file_{i}.txt", 1024, time.ctime()))
        con.commit()
        con.close()
        print(f"Simulated {count} files (Step 24/86).")

    def create_report(self, users: int, tasks: int, files: int, elapsed: float):
        """Step 30: Create stress test report."""
        report = {
            "users": users,
            "tasks": tasks,
            "files": files,
            "total_time_s": elapsed,
            "ops_per_sec": (users + tasks + files) / elapsed
        }
        report_path = Path("logs/reports/stress_test_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {report_path}")

if __name__ == "__main__":
    from app.config import Config
    tester = StressTester(Config.CORE_DB)
    tester.run_stress_test()
