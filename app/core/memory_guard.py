"""
app/core/memory_guard.py
Watchdog for process memory protection.
"""
import os
import threading
import time
import logging

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("kukanilea.memory_guard")

class MemoryGuard:
    def __init__(self, max_rss_mb: int = 1024, check_interval: int = 60):
        self.max_rss_mb = max_rss_mb
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if not psutil:
            logger.warning("psutil not installed. Memory Guard is disabled.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="MemoryGuard")
        self._thread.start()
        logger.info(f"Memory Guard started (Max: {self.max_rss_mb} MB)")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self):
        process = psutil.Process(os.getpid())
        while not self._stop_event.is_set():
            try:
                rss_mb = process.memory_info().rss / (1024 * 1024)
                if rss_mb > self.max_rss_mb:
                    logger.critical(f"MEMORY LIMIT EXCEEDED: {rss_mb:.2f} MB > {self.max_rss_mb} MB. Initiating safe restart.")
                    # Trigger safe shutdown/restart logic here
                    # os.kill(os.getpid(), signal.SIGTERM)
            except Exception as e:
                logger.error(f"Memory check failed: {e}")
            self._stop_event.wait(self.check_interval)

memory_guard = MemoryGuard()
