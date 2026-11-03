"""
Bottle HTTP API application for Variant 18.

Implements all 11 endpoints from Table 18 with RFC 7617 Basic Authentication,
JSON serialization, subprocess integration and report generation.
"""

import base64
from functools import wraps
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable
from bottle import Bottle, request, response
from src.constants import (
    AUTH_HEADER_PREFIX,
    BASIC_REALM,
    DEFAULT_CACHE_HIT,
    DEFAULT_DURATION,
    DEFAULT_PASSWORD,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    ZERO_VAL,
)
from src.storage import SqliteStorage


def verify_auth(expected_user: str, expected_pwd: str) -> bool:
    """Validate RFC 7617 HTTP Basic authentication credentials."""
    auth_header = request.get_header("Authorization", "")
    if not auth_header.startswith(AUTH_HEADER_PREFIX):
        return False
    encoded_token = auth_header[len(AUTH_HEADER_PREFIX):]
    try:
        decoded = base64.b64decode(encoded_token).decode("utf-8")
        user, pwd = decoded.split(":", 1)
        return user == expected_user and pwd == expected_pwd
    except Exception:
        return False


def make_json_response(data: Any, status_code: int = HTTP_OK) -> str:
    """Format JSON payload and set response headers."""
    response.status = status_code
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def run_computational_task(argument: str) -> tuple[str, str, int, bool]:
    """Execute computational CLI tool via subprocess standard module."""
    is_temp = False
    if os.path.exists(argument):
        target_path = argument
    else:
        is_temp = True
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(argument)
            target_path = tmp_file.name

    start_time = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.cli", target_path],
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        is_success = proc.returncode == ZERO_VAL
        return (
            proc.stdout.strip(),
            proc.stderr.strip(),
            duration_ms,
            is_success,
        )
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        return ("", str(exc), duration_ms, False)
    finally:
        if is_temp and os.path.exists(target_path):
            os.remove(target_path)


def build_auth_decorator(user: str, pwd: str) -> Callable:
    """Build authorization decorator for routes."""

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        def wrapper(*args, **kwargs):
            if not verify_auth(user, pwd):
                response.status = HTTP_UNAUTHORIZED
                realm_hdr = f'Basic realm="{BASIC_REALM}"'
                response.set_header("WWW-Authenticate", realm_hdr)
                return make_json_response(
                    {"error": "Unauthorized"}, HTTP_UNAUTHORIZED
                )
            return handler(*args, **kwargs)

        return wrapper

    return decorator


def register_member_routes(
    app: Bottle, db: SqliteStorage, auth_dec: Callable
) -> None:
    """Register Member endpoints (routes 1.1 - 1.4)."""

    @app.route("/public/api/v2/member/store/<uid:int>", method="PUT")
    @auth_dec
    def handle_store_member(uid: int) -> str:
        payload = request.json or {}
        ip_val = payload.get("ip", "")
        ua_val = payload.get("user_agent", "")
        res = db.store_member(uid, ip_val, ua_val)
        return make_json_response(res)

    @app.route("/public/api/v2/member/show", method="GET")
    @auth_dec
    def handle_show_member() -> str:
        params = dict(request.query.decode())
        res = db.find_members(params) if params else db.show_members()
        return make_json_response(res)

    @app.route("/public/api/v2/member/find", method="GET")
    @auth_dec
    def handle_find_member() -> str:
        params = dict(request.query.decode())
        res = db.find_members(params)
        return make_json_response(res)

    @app.route("/public/api/v2/member/correct/<uid:int>", method="PATCH")
    @auth_dec
    def handle_correct_member(uid: int) -> str:
        payload = request.json or {}
        res = db.correct_member(uid, payload)
        return make_json_response(res)


def make_store_instruction_handler(
    db: SqliteStorage, test_mode: bool
) -> Callable:
    """Build handler for PUT /public/api/v2/instruction/store/:id."""

    def handler(uid: int) -> str:
        payload = request.json or {}
        arg_val = payload.get("argument", "")
        mem_val = int(payload.get("member", ZERO_VAL))
        desc_val = payload.get("description", "")
        state_val = payload.get("state", "active")
        inst = db.store_instruction(uid, arg_val, mem_val, desc_val, state_val)
        resp_id = db.get_next_response_id()
        if test_mode:
            resp_dict = {
                "response": "TEST_MODE_OUTPUT",
                "state": "COMPLETED",
                "error": "",
                "instruction": uid,
                "cache_hit": DEFAULT_CACHE_HIT,
                "duration": DEFAULT_DURATION,
            }
        else:
            out_txt, err_txt, dur, ok = run_computational_task(arg_val)
            resp_dict = {
                "response": out_txt,
                "state": "COMPLETED" if ok else "FAILED",
                "error": err_txt,
                "instruction": uid,
                "cache_hit": DEFAULT_CACHE_HIT,
                "duration": dur,
            }
        db.store_response(resp_id, resp_dict)
        return make_json_response(inst)

    return handler


def register_instruction_routes(
    app: Bottle, db: SqliteStorage, auth_dec: Callable, test_mode: bool
) -> None:
    """Register Instruction endpoints (routes 2.1 - 2.4)."""
    store_handler = auth_dec(make_store_instruction_handler(db, test_mode))
    app.route(
        "/public/api/v2/instruction/store/<uid:int>",
        method="PUT",
        callback=store_handler,
    )

    @app.route("/public/api/v2/instruction/show/<member:int>", method="GET")
    @auth_dec
    def handle_show_instruction(member: int) -> str:
        res = db.show_instructions_by_member(member)
        return make_json_response(res)

    @app.route("/public/api/v2/instruction/find", method="GET")
    @auth_dec
    def handle_find_instruction() -> str:
        params = dict(request.query.decode())
        res = db.find_instructions(params)
        return make_json_response(res)

    @app.route("/public/api/v2/instruction/correct/<uid:int>", method="PATCH")
    @auth_dec
    def handle_correct_instruction(uid: int) -> str:
        payload = request.json or {}
        res = db.correct_instruction(uid, payload)
        return make_json_response(res)


def register_response_and_report_routes(
    app: Bottle, db: SqliteStorage, auth_dec: Callable
) -> None:
    """Register Response and Report endpoints (routes 3.1 - 4.1)."""

    @app.route("/public/api/v2/response/show/<instruction:int>", method="GET")
    @auth_dec
    def handle_show_response(instruction: int) -> str:
        res = db.show_responses_by_instruction(instruction)
        return make_json_response(res)

    @app.route("/public/api/v2/response/find", method="GET")
    @auth_dec
    def handle_find_response() -> str:
        params = dict(request.query.decode())
        res = db.find_responses(params)
        return make_json_response(res)

    @app.route("/public/api/v2/report/show", method="GET")
    @auth_dec
    def handle_show_report() -> str:
        report_data = db.get_report()
        return make_json_response(report_data)


def create_app(
    storage: SqliteStorage | None = None,
    username: str = DEFAULT_USERNAME,
    password: str = DEFAULT_PASSWORD,
    test_mode: bool = True,
) -> Bottle:
    """Construct and configure Bottle web application instance."""
    app = Bottle()
    db = storage if storage is not None else SqliteStorage()
    auth_decorator = build_auth_decorator(username, password)
    register_member_routes(app, db, auth_decorator)
    register_instruction_routes(app, db, auth_decorator, test_mode)
    register_response_and_report_routes(app, db, auth_decorator)
    return app
