from __future__ import annotations

import contextlib
import signal
import threading


@contextlib.contextmanager
def time_limit(seconds: int):
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    if hasattr(signal, "SIGALRM"):

        def _handler(signum, frame):
            raise TimeoutError("request timeout")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        yield
