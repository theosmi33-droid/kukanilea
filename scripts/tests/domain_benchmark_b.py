import sys
import time
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app import create_app
from app.agents.orchestrator import MessengerAgent, MailAgent
from app.agents.base import AgentContext

def benchmark_messenger():
    print("\n--- Benchmarking MessengerAgent ---")
    from app.core.tool_loader import load_all_tools
    from app.tools.registry import registry
    load_all_tools()
    print(f"Registered tools: {registry.list()}")
    
    agent = MessengerAgent()
    context = AgentContext(tenant_id="test", user="test", role="USER")
    
    messages = [
        "Hallo",
        "Schicke eine Nachricht via Telegram",
        "@kukanilea erstelle einen Task aus dieser Nachricht",
        "Suche Dokumente für Kunde Müller"
    ]
    
    for msg in messages:
        start = time.perf_counter()
        res = agent.handle(msg, "messenger", context)
        end = time.perf_counter()
        latency = (end - start) * 1000
        print(f"Msg: '{msg[:30]}...' | Latency: {latency:.2f}ms | Actions: {len(res.actions)} | Proposals: {len(res.data.get('hub', {}).get('proposals', []))}")

def benchmark_mail():
    print("\n--- Benchmarking MailAgent ---")
    agent = MailAgent()
    context = AgentContext(tenant_id="test", user="test", role="OPERATOR")
    
    messages = [
        "Status Mail?",
        "Schicke die Mail an den Kunden",
        "Erstelle Entwurf für Rechnung"
    ]
    
    for msg in messages:
        start = time.perf_counter()
        res = agent.handle(msg, "mail", context)
        end = time.perf_counter()
        latency = (end - start) * 1000
        print(f"Msg: '{msg[:30]}...' | Latency: {latency:.2f}ms | Actions: {len(res.actions)}")

def benchmark_chatbot_api():
    print("\n--- Benchmarking Chatbot API (Compact) ---")
    app = create_app()
    with app.app_context():
        from app.web import api_chat_compact
        from flask import Flask, session, request
        
        # Mock request context with CSRF bypass for benchmark
        with app.test_request_context(
            '/api/chat/compact',
            method='POST',
            data=json.dumps({"message": "Was kannst du tun?", "current_context": "/dashboard"}),
            content_type='application/json',
            headers={'X-CSRF-Token': 'bench-token'}
        ):
            # Set session
            session['user'] = 'dev'
            session['role'] = 'DEV'
            session['tenant_id'] = 'KUKANILEA'
            session['csrf_token'] = 'bench-token'
            
            # Monkeypatch login_required and csrf_protected for benchmark if needed, 
            # but setting session/header should be enough if using app.test_request_context
            
            start = time.perf_counter()
            try:
                resp = api_chat_compact()
                end = time.perf_counter()
                latency = (end - start) * 1000
                print(f"API Compact: /dashboard | Latency: {latency:.2f}ms | Status: {resp.status_code}")
            except Exception as e:
                print(f"API Compact failed: {e}")

if __name__ == "__main__":
    benchmark_messenger()
    benchmark_mail()
    benchmark_chatbot_api()
