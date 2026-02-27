#!/usr/bin/env python3
"""KUKANILEA – Single Entry Point (v1.3.1)"""
import argparse
import logging
import sys
import time
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def handle_sigterm(signum, frame):
    logger.info("🛑 Received SIGTERM. Commencing safe shutdown sequence...")
    # Add hooks to close DB connections, agents, thread pools here safely.
    from app.core.task_queue import task_queue
    from app.core.memory_guard import memory_guard
    from app.core.thread_monitor import thread_monitor
    try:
        task_queue.stop()
        memory_guard.stop()
        thread_monitor.stop()
    except Exception: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

def main():
    start_time = time.time()
    
    parser = argparse.ArgumentParser(prog='kukanilea', description='KUKANILEA Business OS')
    parser.add_argument('--mode', choices=['full', 'api', 'web'], default='full')
    parser.add_argument('--port', type=int, default=5051)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--benchmark', action='store_true', help="Run startup benchmark and exit")
    parser.add_argument('--version', action='version', version='1.1.0-RC')
    args = parser.parse_args()
    
    logger.info("🚀 Initializing KUKANILEA v1.1.0-RC (Fleet Commander)...")
    
    from app import create_app
    app = create_app()
    
    # 1. Config Validation
    from app.core.config_schema import validate_config
    from app.config import Config
    if not validate_config({k: v for k, v in Config.__dict__.items() if not k.startswith('_')}):
        logger.critical("Configuration validation failed. Blocking startup.")
        sys.exit(1)
        
    # 2. Sequential Migrations
    from app.core.migrations import run_migrations
    run_migrations(Config.CORE_DB)
    
    # 3. System Self-Test (WORM, Storage, DB, ClamAV)
    from app.core.selftest import run_selftest
    if not run_selftest({k: v for k, v in Config.__dict__.items() if not k.startswith('_')}):
        logger.critical("Self-test failed. Blocking startup.")
        sys.exit(1)
        
    # 4. Watchdogs & Queues Start
    from app.core.task_queue import task_queue
    from app.core.memory_guard import memory_guard
    from app.core.thread_monitor import thread_monitor
    task_queue.start()
    memory_guard.start()
    thread_monitor.start()

    boot_duration = (time.time() - start_time) * 1000
    logger.info(f"✅ Boot sequence completed in {boot_duration:.2f}ms")
    
    if args.benchmark:
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info().rss / (1024 * 1024)
            print(f"BENCHMARK: BootTime={boot_duration:.2f}ms, MemoryUsage={mem_info:.2f}MB")
        except ImportError:
            print(f"BENCHMARK: BootTime={boot_duration:.2f}ms, MemoryUsage=Unknown")
        sys.exit(0)
    
    if args.mode == 'api':
        app.config['WEB_ENABLED'] = False
        logger.info(f"🔌 API-only mode on {args.host}:{args.port}")
    elif args.mode == 'web':
        app.config['API_ENABLED'] = False
        logger.info(f"🌐 Web-only mode on {args.host}:{args.port}")
    else:
        logger.info(f"⚡ Full-Stack mode on {args.host}:{args.port}")
    
    try:
        if not args.debug:
            try:
                from waitress import serve
                logger.info(f"⚡ Starting production-ready server (Waitress) on {args.host}:{args.port}")
                serve(app, host=args.host, port=args.port, threads=8, max_request_body_size=100*1024*1024)
            except ImportError:
                logger.warning("Waitress not found, falling back to Flask dev server.")
                app.run(host=args.host, port=args.port, debug=args.debug)
        else:
            app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        task_queue.stop()
        memory_guard.stop()
        thread_monitor.stop()
        sys.exit(0)

if __name__ == '__main__':
    main()
