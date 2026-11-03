"""
HTTP API client for Variant 18 web application.

Method names strictly follow the 'действие_таблица' convention defined
in Requirement 4 of the variant specification.
"""

import base64
import io
import json
import urllib.parse
import urllib.request
import wsgiref.util
from typing import Any
from bottle import Bottle
from src.constants import (
    AUTH_HEADER_PREFIX,
    DEFAULT_PASSWORD,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    DEFAULT_USERNAME,
    HTTP_OK,
    ZERO_VAL,
)


class ApiClient:
    """
    Client for interacting with the Variant 18 HTTP API.

    Can operate against a live HTTP URL or directly via WSGI app.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        app: Bottle | None = None,
    ):
        """Configure client network target and Basic Auth credentials."""
        default_url = f"http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}"
        self.base_url = base_url if base_url is not None else default_url
        self.username = username
        self.password = password
        self.app = app
        self.last_status = HTTP_OK

    def _get_auth_header(self) -> str:
        """Construct RFC 7617 Authorization header value."""
        raw = f"{self.username}:{self.password}".encode("utf-8")
        token = base64.b64encode(raw).decode("utf-8")
        return f"{AUTH_HEADER_PREFIX}{token}"

    def _request_wsgi(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None,
        body: dict[str, Any] | None,
    ) -> Any:
        """Dispatch request directly to WSGI application."""
        query_string = urllib.parse.urlencode(query or {})
        body_bytes = json.dumps(body or {}).encode("utf-8") if body else b""
        status_box = [HTTP_OK]

        def start_response(status_line: str, headers: Any, exc: Any = None):
            status_box[ZERO_VAL] = int(status_line.split()[ZERO_VAL])

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(body_bytes)),
            "HTTP_AUTHORIZATION": self._get_auth_header(),
            "wsgi.input": io.BytesIO(body_bytes),
            "wsgi.errors": io.StringIO(),
        }
        wsgiref.util.setup_testing_defaults(environ)
        output_iterable = self.app(environ, start_response)
        raw_output = b"".join(output_iterable)
        self.last_status = status_box[ZERO_VAL]
        try:
            return json.loads(raw_output.decode("utf-8"))
        except Exception:
            return raw_output.decode("utf-8")

    def _request_http(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None,
        body: dict[str, Any] | None,
    ) -> Any:
        """Perform real HTTP request using standard urllib."""
        query_string = urllib.parse.urlencode(query or {})
        url = f"{self.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        body_bytes = json.dumps(body or {}).encode("utf-8") if body else None
        req = urllib.request.Request(url=url, data=body_bytes, method=method)
        req.add_header("Authorization", self._get_auth_header())
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                self.last_status = resp.status
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            self.last_status = error.code
            try:
                return json.loads(error.read().decode("utf-8"))
            except Exception:
                return {"error": str(error)}

    def request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Route request through WSGI or HTTP transport."""
        if self.app is not None:
            return self._request_wsgi(method, path, query, body)
        return self._request_http(method, path, query, body)

    def store_member(self, uid: int, data: dict[str, Any]) -> Any:
        """Store member entity (PUT /public/api/v2/member/store/:id)."""
        return self.request(
            "PUT", f"/public/api/v2/member/store/{uid}", body=data
        )

    def show_member(self, params: dict[str, Any] | None = None) -> Any:
        """Retrieve members (GET /public/api/v2/member/show)."""
        return self.request("GET", "/public/api/v2/member/show", query=params)

    def find_member(self, params: dict[str, Any] | None = None) -> Any:
        """Find members by query (GET /public/api/v2/member/find)."""
        return self.request("GET", "/public/api/v2/member/find", query=params)

    def correct_member(self, uid: int, data: dict[str, Any]) -> Any:
        """Correct member entity (PATCH /public/api/v2/member/correct/:id)."""
        return self.request(
            "PATCH", f"/public/api/v2/member/correct/{uid}", body=data
        )

    def store_instruction(self, uid: int, data: dict[str, Any]) -> Any:
        """Store instruction (PUT /public/api/v2/instruction/store/:id)."""
        return self.request(
            "PUT", f"/public/api/v2/instruction/store/{uid}", body=data
        )

    def show_instruction(
        self, member: int, params: dict[str, Any] | None = None
    ) -> Any:
        """Show instructions (GET /public/api/v2/instruction/show/:member)."""
        return self.request(
            "GET",
            f"/public/api/v2/instruction/show/{member}",
            query=params,
        )

    def find_instruction(self, params: dict[str, Any] | None = None) -> Any:
        """Find instructions (GET /public/api/v2/instruction/find)."""
        return self.request(
            "GET", "/public/api/v2/instruction/find", query=params
        )

    def correct_instruction(self, uid: int, data: dict[str, Any]) -> Any:
        """Correct instruction (PATCH /public/api/v2/instruction/correct)."""
        return self.request(
            "PATCH", f"/public/api/v2/instruction/correct/{uid}", body=data
        )

    def show_response(
        self, instruction: int, params: dict[str, Any] | None = None
    ) -> Any:
        """Show response (GET /public/api/v2/response/show/:instruction)."""
        return self.request(
            "GET",
            f"/public/api/v2/response/show/{instruction}",
            query=params,
        )

    def find_response(self, params: dict[str, Any] | None = None) -> Any:
        """Find responses by query (GET /public/api/v2/response/find)."""
        return self.request(
            "GET", "/public/api/v2/response/find", query=params
        )

    def show_report(self) -> Any:
        """Retrieve formula 18 report (GET /public/api/v2/report/show)."""
        return self.request("GET", "/public/api/v2/report/show")
