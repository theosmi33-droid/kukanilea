"""
app/core/task_queue.py
Background worker queue for non-blocking operations.
"""
import queue
import threading
import logging
from typing import Callable, Any, Tuple

logger = logging.getLogger("kukanilea.task_queue")

class BackgroundTaskQueue:
    def __init__(self, num_workers: int = 4):
        self.q = queue.Queue()
        self.workers = []
        self.num_workers = num_workers
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"Worker-{i}", daemon=True)
            t.start()
            self.workers.append(t)
        logger.info(f"Started Task Queue with {self.num_workers} workers.")

    def stop(self):
        self._stop_event.set()
        # Send sentinel values to unblock workers
        for _ in range(self.num_workers):
            self.q.put((None, None, None))
        for t in self.workers:
            t.join(timeout=2.0)
        self.workers.clear()
        logger.info("Task Queue stopped.")

    def submit(self, func: Callable, *args, **kwargs):
        self.q.put((func, args, kwargs))

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self.q.get(timeout=1.0)
                if item == (None, None, None):
                    self.q.task_done()
                    break
                
                func, args, kwargs = item
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Task failed in background queue: {e}", exc_info=True)
                finally:
                    self.q.task_done()
            except queue.Empty:
                continue

# Global Instance
task_queue = BackgroundTaskQueue()
