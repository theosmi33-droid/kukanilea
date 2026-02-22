import asyncio
import httpx
import time
import json
import os
from pathlib import Path

# Config
BASE_URL = "http://127.0.0.1:8000"
TOTAL_REQUESTS = 5000
CONCURRENCY = 50

async def stress_worker(client, stats):
    targets = [
        {"method": "GET", "url": "/health"},
        {"method": "GET", "url": "/crm/"},
        {"method": "GET", "url": "/tasks/"},
        {"method": "POST", "url": "/ui/onboarding/setup", "data": {"vertical": "dach"}}
    ]
    
    for _ in range(TOTAL_REQUESTS // CONCURRENCY):
        for target in targets:
            start = time.perf_counter()
            try:
                headers = {"X-Tenant-ID": "stress-tenant", "X-User-ID": "bot", "X-Role": "ADMIN"}
                if target["method"] == "GET":
                    resp = await client.get(target["url"], headers=headers, timeout=10.0)
                else:
                    resp = await client.post(target["url"], data=target["data"], headers=headers, timeout=10.0)
                
                latency = (time.perf_counter() - start) * 1000
                stats["latencies"].append(latency)
                stats["status_codes"][resp.status_code] = stats["status_codes"].get(resp.status_code, 0) + 1
                
            except Exception as e:
                stats["errors"] += 1
                stats["error_types"][type(e).__name__] = stats["error_types"].get(type(e).__name__, 0) + 1

async def main():
    print(f"Starting Stress Test against {BASE_URL}...")
    stats = {"latencies": [], "status_codes": {}, "errors": 0, "error_types": {}}
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        workers = [stress_worker(client, stats) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)
    
    # Calculate Results
    avg_latency = sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0
    p99_latency = sorted(stats["latencies"])[int(len(stats["latencies"]) * 0.99)] if stats["latencies"] else 0
    
    report = {
        "total_requests": len(stats["latencies"]),
        "errors": stats["errors"],
        "error_types": stats["error_types"],
        "status_codes": stats["status_codes"],
        "avg_latency_ms": round(avg_latency, 2),
        "p99_latency_ms": round(p99_latency, 2)
    }
    
    os.makedirs("dist/evidence", exist_ok=True)
    with open("dist/evidence/stress_test_report.json", "w") as f:
        json.dump(report, f, indent=4)
    
    print("
--- STRESS TEST COMPLETE ---")
    print(json.dumps(report, indent=4))

if __name__ == "__main__":
    # Hinweis: Erfordert laufenden Server via uvicorn kukanilea_app:app
    asyncio.run(main())
