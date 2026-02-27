from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("kukanilea.lifecycle")

class SystemState(enum.Enum):
    BOOT = "BOOT"
    INIT = "INIT"
    READY = "READY"
    ERROR = "ERROR"

class LifecycleManager:
    _instance: Optional[LifecycleManager] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LifecycleManager, cls).__new__(cls)
                cls._instance._state = SystemState.BOOT
                cls._instance._start_time = time.time()
                cls._instance._details = "System kernel starting..."
                cls._instance._errors = []
            return cls._instance

    @property
    def state(self) -> SystemState:
        return self._state

    @property
    def details(self) -> str:
        return self._details

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time

    def set_state(self, state: SystemState, details: str = ""):
        now = time.time()
        elapsed = now - self._start_time
        logger.info(f"System State Change: {self._state.value} -> {state.value} ({details}) [T+{elapsed:.3f}s]")
        
        # Performance Milestone Log
        if state == SystemState.READY:
            logger.info(f"🚀 KUKANILEA READY. Full boot time: {elapsed:.3f}s")
            
        self._state = state
        self._details = details

    def report_error(self, error: str):
        self._errors.append(error)
        self.set_state(SystemState.ERROR, f"Last error: {error}")

manager = LifecycleManager()
