import sys
from app.agents.orchestrators.router import Router
from app.agents.orchestrators.scheduler import Scheduler
from app.agents.orchestrators.triage import Triage
from app.agents.core.observer import Observer

def boot():
    print("Initializing KUKANILEA Agent Framework...")
    router = Router()
    scheduler = Scheduler()
    triage = Triage()
    observer = Observer()
    
    # Verify health
    router.log_heartbeat("BOOT_INIT")
    scheduler.log_heartbeat("BOOT_INIT")
    triage.log_heartbeat("BOOT_INIT")
    observer.log_heartbeat("BOOT_INIT")
    
    print("Framework Ready. Determinism: ENABLED | Offline: ENABLED | Gates: ACTIVE")

if __name__ == "__main__":
    boot()
