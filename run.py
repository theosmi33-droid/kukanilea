#!/usr/bin/env python3
"""
KUKANILEA Systems — Central Entry Point (run.py)
==============================================
Consolidates all start-up processes (Server, Maintenance, Audit).
Enforces the Zero-Tolerance Development Path (Quality Gate 3).

Usage:
  python run.py server [--port 5051] [--host 127.0.0.1]
  python run.py maintenance
  python run.py audit
  python run.py chaos
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add current directory to sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.append(str(PROJECT_ROOT))


def start_server(port: int, host: str):
    """Starts the main KUKANILEA Flask Application."""
    from app import create_app
    import threading
    import time
    import os
    import socket

    def watchdog_ping():
        """Pings systemd watchdog if NOTIFY_SOCKET is present."""
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            return
        
        if notify_socket.startswith("@"):
            notify_socket = "\0" + notify_socket[1:]
            
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                # Tell systemd we are ready
                sock.sendto(b"READY=1", notify_socket)
                
                # Periodically ping the watchdog
                while True:
                    sock.sendto(b"WATCHDOG=1", notify_socket)
                    time.sleep(10)  # Ping every 10 seconds (must be < WatchdogSec)
        except Exception as e:
            print(f"⚠️ Watchdog ping failed: {e}")

    app = create_app()
    print(f"🚀 KUKANILEA Enterprise Server starting on http://{host}:{port}")
    
    # Start the watchdog thread (daemon so it exits when main app exits)
    threading.Thread(target=watchdog_ping, daemon=True).start()
    
    # Switch to production-ready WSGI server: Waitress
    from waitress import serve
    serve(app, host=host, port=port, threads=8, max_request_body_size=100*1024*1024) # 100MB limit


def run_maintenance():
    """Runs the daily maintenance daemon."""
    script_path = PROJECT_ROOT / "scripts" / "ops" / "maintenance_daemon.sh"
    if script_path.exists():
        print("🛠️ Running Maintenance Daemon...")
        subprocess.run(["bash", str(script_path)], check=True)
    else:
        print(
            "❌ Error: Maintenance script not found at scripts/ops/maintenance_daemon.sh"
        )
        sys.exit(1)


def run_security_audit():
    """Runs the supply-chain security audit."""
    script_path = PROJECT_ROOT / "scripts" / "ops" / "security_scan.py"
    if script_path.exists():
        print("🛡️ Starting Supply-Chain Security Audit...")
        subprocess.run([sys.executable, str(script_path)], check=True)
    else:
        print("❌ Error: Security scan script not found.")
        sys.exit(1)


def run_chaos_monkey():
    """Runs the weekly chaos & resilience tests."""
    script_path = PROJECT_ROOT / "scripts" / "tests" / "chaos_monkey.py"
    if script_path.exists():
        print("🐒 Starting KUKANILEA Chaos Monkey (Resilience Test)...")
        subprocess.run([sys.executable, str(script_path)], check=True)
    else:
        print("❌ Error: Chaos Monkey script not found.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="KUKANILEA Systems - Central Control Unit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Operational command")

    # Command: server
    server_parser = subparsers.add_parser("server", help="Start the main UI/API server")
    server_parser.add_argument(
        "--port", type=int, default=5051, help="Port (default: 5051)"
    )
    server_parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)"
    )

    # Command: maintenance
    subparsers.add_parser("maintenance", help="Run maintenance & vacuum")

    # Command: audit
    subparsers.add_parser("audit", help="Run supply-chain security scan")

    # Command: chaos
    subparsers.add_parser("chaos", help="Run chaos & resilience tests")

    args = parser.parse_args()

    # Default to server if no command provided (useful for bundled apps)
    if not args.command:
        args.command = "server"
        args.port = 5051
        args.host = "127.0.0.1"

    try:
        if args.command == "server":
            start_server(args.port, args.host)
        elif args.command == "maintenance":
            run_maintenance()
        elif args.command == "audit":
            run_security_audit()
        elif args.command == "chaos":
            run_chaos_monkey()
        else:
            parser.print_help()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
