"""
Agent Bridge Service - Main entry point.

This service enables two voice agents to have a real-time conversation with each other
by acting as a bridge between their WebSocket connections.

Usage:
    python main.py                    # Run with defaults (host=0.0.0.0, port=8080)
    python main.py --host 127.0.0.1   # Custom host
    python main.py --port 9000        # Custom port
"""

import argparse
import logging

import uvicorn
from dotenv import load_dotenv

from api.app import app
from utils.logger import get_logger, setup_logging

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Agent Bridge Service - Connect two voice agents for conversation")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the server on (default: 8080)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Convert uvicorn log level format to logging level
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    log_level = log_level_map.get(args.log_level.lower(), logging.INFO)

    # Setup logging with the specified level
    setup_logging(log_level=log_level)

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║                   Agent Bridge Service                       ║")
    logger.info("║                                                              ║")
    logger.info("║  Enables two voice agents to have a real-time conversation   ║")
    logger.info("╚══════════════════════════════════════════════════════════════╝")
    logger.info("")
    logger.info(f"Server starting on http://{args.host}:{args.port}")
    logger.info(f"API docs available at http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "api.app:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
