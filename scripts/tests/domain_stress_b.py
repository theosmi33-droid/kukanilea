import sys
import time
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.append(str(Path(__file__).parent.parent.parent))

from app import create_app
from app.agents.orchestrator import MessengerAgent
from app.agents.base import AgentContext

# Benchmark results from previous run
# API Compact: ~20ms
# Messenger heuristic: <1ms
# Messenger agentic: ~1.8s

def stress_messenger_heuristic(tenant_id, iterations=50):
    agent = MessengerAgent()
    context = AgentContext(tenant_id=tenant_id, user="stress_user", role="USER")
    success = 0
    for i in range(iterations):
        try:
            res = agent.handle("Schicke Nachricht via Telegram", "messenger", context)
            if "proposals" in res.data.get("hub", {}):
                success += 1
        except Exception as e:
            print(f"Messenger Stress Error: {e}")
    return success

def stress_chatbot_api(app, iterations=50):
    success = 0
    with app.app_context():
        from app.web import api_chat_compact
        from flask import session
        
        for i in range(iterations):
            with app.test_request_context(
                '/api/chat/compact',
                method='POST',
                data=json.dumps({"message": f"Stress test msg {i}", "current_context": "/"}),
                content_type='application/json',
                headers={'X-CSRF-Token': 'stress-token'}
            ):
                session['user'] = 'stress_user'
                session['role'] = 'USER'
                session['tenant_id'] = 'STRESS_TENANT'
                session['csrf_token'] = 'stress-token'
                
                try:
                    resp = api_chat_compact()
                    if resp.status_code == 200:
                        success += 1
                except Exception as e:
                    print(f"API Stress Error: {e}")
    return success

def run_intense_stress():
    print("--- WORKER B: Intense Stress Test & Debug ---")
    app = create_app()
    
    # 1. Parallel Messenger Agent Stress (Database IO focus)
    print("Phase 1: Concurrent Messenger Agent (10 threads, 500 total requests)...")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(stress_messenger_heuristic, f"TENANT_{i%3}") for i in range(10)]
        results = [f.result() for f in futures]
    end = time.perf_counter()
    print(f"Phase 1 Complete. Success rate: {sum(results)}/500 | Duration: {end-start:.2f}s")

    # 2. Parallel API Stress (Session & Request Context focus)
    print("\nPhase 2: Concurrent API Compact (5 threads, 100 total requests)...")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(stress_chatbot_api, app, 20) for _ in range(5)]
        results = [f.result() for f in futures]
    end = time.perf_counter()
    print(f"Phase 2 Complete. Success rate: {sum(results)}/100 | Duration: {end-start:.2f}s")

if __name__ == "__main__":
    run_intense_stress()
