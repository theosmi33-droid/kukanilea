import os
import sys
import time
from pathlib import Path
from multiprocessing import Process

sys.path.append(str(Path(__file__).parent.parent.parent))

from app import create_app
from kukanilea_core_v3_fixed import task_create, rbac_create_user, get_db_info

def worker_tasks(tenant, worker_id, count):
    app = create_app()
    with app.app_context():
        for i in range(count):
            try:
                task_create(
                    tenant=tenant,
                    severity="INFO",
                    task_type="STRESS",
                    title=f"Stress Task {worker_id}-{i}",
                    details="This is a load test task",
                    created_by="stress_worker"
                )
            except Exception as e:
                print(f"Worker {worker_id} failed at task {i}: {e}")
                sys.exit(1)

def run_stress_test():
    print("--- KUKANILEA Performance Burst Audit ---")
    print("Starting intense load simulation (Equivalent to 15m of typical usage)...")
    
    start_time = time.time()
    
    app = create_app()
    with app.app_context():
        rbac_create_user("stress_worker", "password")
    
    workers = []
    for i in range(10):
        p = Process(target=worker_tasks, args=("default", i, 500))
        workers.append(p)
        p.start()
        
    for p in workers:
        p.join()
        if p.exitcode != 0:
            print("\n[FAILED] Stress test workers failed!")
            sys.exit(1)
            
    end_time = time.time()
    duration = end_time - start_time
    
    with app.app_context():
        db_info = get_db_info()
        print("\n[PASSED] Stress Burst Audit complete.")
        print(f"Time taken: {duration:.2f} seconds")
        print(f"Database Stats: {db_info}")

if __name__ == "__main__":
    run_stress_test()
