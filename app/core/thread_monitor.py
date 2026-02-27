"""
app/core/thread_monitor.py
Deadlock detection and thread monitoring.
"""
import threading
import time
import sys
import traceback
import logging

logger = logging.getLogger("kukanilea.thread_monitor")

class ThreadMonitor:
    def __init__(self, check_interval: int = 300):
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ThreadMonitor")
        self._thread.start()
        logger.info("Thread Monitor started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                active_threads = threading.enumerate()
                thread_count = len(active_threads)
                
                # If too many threads, log stack traces to debug potential leaks
                if thread_count > 50:
                    logger.warning(f"High thread count detected: {thread_count}")
                    self._dump_threads()
                    
            except Exception as e:
                logger.error(f"Thread monitor failed: {e}")
            self._stop_event.wait(self.check_interval)

    def _dump_threads(self):
        for th in threading.enumerate():
            logger.debug(f"Thread: {th.name} ({th.ident})")
            if th.ident in sys._current_frames():
                frame = sys._current_frames()[th.ident]
                logger.debug("".join(traceback.format_stack(frame)))

thread_monitor = ThreadMonitor()
