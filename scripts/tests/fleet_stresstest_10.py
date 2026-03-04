import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app import create_app

def simulate_user(user_id, app, iterations=20):
    client = app.test_client()
    success = 0
    errors = 0
    
    # Establish session
    with client.session_transaction() as sess:
        sess['user'] = f'user_{user_id}'
        sess['role'] = 'OPERATOR'
        sess['tenant_id'] = 'KUKANILEA'
        sess['csrf_token'] = 'stress-token'

    endpoints = [
        ("/", "GET"),
        ("/messenger", "GET"),
        ("/mail", "GET"),
        ("/api/chat/compact", "POST", {"message": "Hallo", "current_context": "/"}),
        ("/api/search", "POST", {"query": "Test"}),
        ("/upload/upload", "POST", {"file": (Path("/tmp/stress.txt"), "content")}) # Mock file
    ]

    for i in range(iterations):
        route, method, *data = random.choice(endpoints)
        start = time.perf_counter()
        try:
            if method == "GET":
                resp = client.get(route)
            else:
                payload = data[0] if data else {}
                resp = client.post(route, json=payload, headers={'X-CSRF-Token': 'stress-token'})
            
            latency = (time.perf_counter() - start) * 1000
            if resp.status_code in [200, 302]:
                success += 1
            else:
                errors += 1
                print(f"User {user_id} Error {resp.status_code} on {route}: {resp.get_data(as_text=True)}")
        except Exception as e:
            errors += 1
            # print(f"User {user_id} Exception: {e}")
            
        time.sleep(random.uniform(0.1, 0.3)) # Simulating human behavior
        
    return success, errors

def run_fleet_stress():
    print("--- KUKANILEA FLEET: 10 CONCURRENT USERS STRESS TEST ---")
    app = create_app()
    app.config['DEBUG'] = False
    app.config['TESTING'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    
    # Enable stress bypass
    import os
    os.environ["KUKANILEA_DEBUG_STRESS"] = "1"
    
    num_users = 10
    iters_per_user = 30
    
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [executor.submit(simulate_user, i, app, iters_per_user) for i in range(num_users)]
        results = [f.result() for f in futures]
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    total_success = sum(r[0] for r in results)
    total_errors = sum(r[1] for r in results)
    total_reqs = total_success + total_errors
    
    print(f"\nResults:")
    print(f"Total Requests: {total_reqs}")
    print(f"Success: {total_success} ({(total_success/total_reqs)*100:.1f}%)")
    print(f"Errors: {total_errors}")
    print(f"Total Duration: {duration:.2f}s")
    print(f"Throughput: {total_reqs/duration:.2f} req/s")
    print(f"Avg Latency per Request: {(duration*1000)/total_reqs:.2f}ms")

if __name__ == "__main__":
    # Create temp stress file
    with open("/tmp/stress.txt", "w") as f: f.write("stress test")
    run_fleet_stress()
