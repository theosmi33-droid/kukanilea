#!/usr/bin/env python3
"""KUKANILEA – Single Entry Point"""
import argparse, sys, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from app import create_app

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(prog='kukanilea', description='KUKANILEA Business OS')
    parser.add_argument('--mode', choices=['full', 'api', 'web'], default='full')
    parser.add_argument('--port', type=int, default=5051)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--version', action='version', version='1.0.0-beta.3')
    args = parser.parse_args()
    
    logger.info("🚀 Initializing KUKANILEA...")
    app = create_app()
    
    if args.mode == 'api':
        app.config['WEB_ENABLED'] = False
        logger.info(f"🔌 API-only mode on {args.host}:{args.port}")
    elif args.mode == 'web':
        app.config['API_ENABLED'] = False
        logger.info(f"🌐 Web-only mode on {args.host}:{args.port}")
    else:
        logger.info(f"⚡ Full-Stack mode on {args.host}:{args.port}")
    
    try:
        # Check if we should use waitress or dev server
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
        sys.exit(0)

if __name__ == '__main__':
    main()
