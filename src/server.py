"""
Server launcher for Variant 18 Bottle web application.

Parses command-line arguments for RFC 7617 credentials, port, host,
database path and test mode execution flag.
"""

import argparse
import sys
from bottle import run
from src.app import create_app
from src.constants import (
    DEFAULT_PASSWORD,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    DEFAULT_USERNAME,
)
from src.storage import SqliteStorage


def parse_cli_args(args: list[str]) -> argparse.Namespace:
    """Parse configuration parameters from command line arguments."""
    parser = argparse.ArgumentParser(
        description="Launch Variant 18 Bottle HTTP API Server"
    )
    parser.add_argument(
        "-u",
        "--username",
        default=DEFAULT_USERNAME,
        help="RFC 7617 username",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=DEFAULT_PASSWORD,
        help="RFC 7617 password",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_SERVER_HOST,
        help="Host address to bind",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help="Port number to bind",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run without executing computational subprocess",
    )
    parser.add_argument(
        "--db-path",
        default="app.db",
        help="Path to SQLite database file",
    )
    return parser.parse_args(args)


def run_server(args: list[str] | None = None) -> None:
    """Initialize storage, build application and start HTTP server."""
    cli_args = parse_cli_args(args if args is not None else sys.argv[1:])
    storage = SqliteStorage(cli_args.db_path)
    app = create_app(
        storage=storage,
        username=cli_args.username,
        password=cli_args.password,
        test_mode=cli_args.test_mode,
    )
    run(
        app=app,
        host=cli_args.host,
        port=cli_args.port,
        server="wsgiref",
        quiet=False,
    )


if __name__ == "__main__":
    run_server()
