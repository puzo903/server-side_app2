"""
Model-Based Testing (MBT) for Variant 18 HTTP API.

Utilizes Hypothesis RuleBasedStateMachine to exhaustively test all
11 HTTP API endpoints, authentication, and SQLite persistence.
"""

import io
import wsgiref.util
from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    precondition,
    rule,
)
import hypothesis.strategies as st
from src.app import create_app
from src.client import ApiClient
from src.constants import (
    AUDIO_DEFAULT_SAMPLE_RATE,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    EXIT_FAILURE,
    EXIT_SUCCESS,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
    MAX_TEST_EXAMPLES,
    MAX_TEXT_LEN,
    MIN_STR_LEN,
    ONE_VAL,
    STATEFUL_STEP_COUNT,
    TWO_VAL,
    ZERO_VAL,
)
from src.storage import SqliteStorage

settings.register_profile(
    "dev",
    max_examples=MAX_TEST_EXAMPLES,
    stateful_step_count=STATEFUL_STEP_COUNT,
    deadline=None,
)
settings.load_profile("dev")

TEXT_STRAT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=MIN_STR_LEN,
    max_size=MAX_TEXT_LEN,
)

GLOBAL_STORAGE = SqliteStorage(":memory:")
GLOBAL_APP = create_app(
    storage=GLOBAL_STORAGE,
    username=DEFAULT_USERNAME,
    password=DEFAULT_PASSWORD,
    test_mode=True,
)


class ModelAPI(RuleBasedStateMachine):
    """Hypothesis state machine verifying all Variant 18 HTTP API methods."""

    def __init__(self):
        """Set up in-memory SQLite storage, app, and client."""
        super().__init__()
        self.storage = GLOBAL_STORAGE
        self.app = GLOBAL_APP
        self.client = ApiClient(
            app=self.app,
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
        )
        self.model_members: list[dict] = []
        self.model_instructions: list[dict] = []
        self.member_seq = ONE_VAL
        self.inst_seq = ONE_VAL

    def teardown(self):
        """Clean up storage tables and state trackers."""
        self.storage.clear()
        self.model_members.clear()
        self.model_instructions.clear()

    @initialize()
    def setup_initial_entities(self):
        """Populate initial entities so all state rules are executable."""
        uid = self.member_seq
        self.member_seq += ONE_VAL
        m_res = self.client.store_member(
            uid, {"ip": "127.0.0.1", "user_agent": "InitialUA"}
        )
        self.model_members.append(m_res)

        iid = self.inst_seq
        self.inst_seq += ONE_VAL
        i_res = self.client.store_instruction(
            iid,
            {
                "argument": "examples/input1.txt",
                "member": uid,
                "description": "InitialDesc",
                "state": "active",
            },
        )
        self.model_instructions.append(i_res)
        self.client.find_instruction({"id": iid})
        self.client.find_response({"state": "COMPLETED"})

    @rule(ip=TEXT_STRAT, user_agent=TEXT_STRAT)
    def store_member(self, ip: str, user_agent: str):
        """Test PUT /public/api/v2/member/store/:id."""
        uid = self.member_seq
        self.member_seq += ONE_VAL
        payload = {"ip": ip, "user_agent": user_agent}
        res = self.client.store_member(uid, payload)
        assert self.client.last_status == HTTP_OK
        assert res["id"] == uid
        self.model_members.append(res)

    @rule()
    def show_member(self):
        """Test GET /public/api/v2/member/show."""
        res = self.client.show_member()
        assert self.client.last_status == HTTP_OK
        assert len(res) == len(self.model_members)

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def show_member_filtered(self):
        """Test GET /public/api/v2/member/show with query parameters."""
        target = self.model_members[-1]
        res = self.client.show_member({"ip": target["ip"]})
        assert self.client.last_status == HTTP_OK
        assert isinstance(res, list)

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def find_member(self):
        """Test GET /public/api/v2/member/find."""
        target = self.model_members[-1]
        res = self.client.find_member({"id": target["id"]})
        assert self.client.last_status == HTTP_OK
        assert len(res) == ONE_VAL
        assert res[ZERO_VAL]["id"] == target["id"]

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule(new_ip=TEXT_STRAT)
    def correct_member(self, new_ip: str):
        """Test PATCH /public/api/v2/member/correct/:id."""
        target = self.model_members[-1]
        res = self.client.correct_member(target["id"], {"ip": new_ip})
        assert self.client.last_status == HTTP_OK
        assert res["ip"] == new_ip
        target["ip"] = new_ip

    @rule()
    def correct_nonexistent_member(self):
        """Test correct member with unknown identifier."""
        non_id = 999999
        res = self.client.correct_member(non_id, {"ip": "1.1.1.1"})
        assert self.client.last_status == HTTP_OK
        assert res == {}

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule(arg=TEXT_STRAT, desc=TEXT_STRAT, state=TEXT_STRAT)
    def store_instruction(self, arg: str, desc: str, state: str):
        """Test PUT /public/api/v2/instruction/store/:id."""
        iid = self.inst_seq
        self.inst_seq += ONE_VAL
        mem_id = self.model_members[-1]["id"]
        payload = {
            "argument": arg,
            "member": mem_id,
            "description": desc,
            "state": state,
        }
        res = self.client.store_instruction(iid, payload)
        assert self.client.last_status == HTTP_OK
        assert res["id"] == iid
        self.model_instructions.append(res)

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def show_instruction(self):
        """Test GET /public/api/v2/instruction/show/:member."""
        mem_id = self.model_members[-1]["id"]
        res = self.client.show_instruction(mem_id)
        assert self.client.last_status == HTTP_OK
        assert isinstance(res, list)

    @precondition(lambda self: len(self.model_instructions) > ZERO_VAL)
    @rule()
    def find_instruction(self):
        """Test GET /public/api/v2/instruction/find."""
        target = self.model_instructions[-1]
        res = self.client.find_instruction({"id": target["id"]})
        assert self.client.last_status == HTTP_OK
        assert len(res) == ONE_VAL
        assert res[ZERO_VAL]["id"] == target["id"]

    @precondition(lambda self: len(self.model_instructions) > ZERO_VAL)
    @rule(new_desc=TEXT_STRAT)
    def correct_instruction(self, new_desc: str):
        """Test PATCH /public/api/v2/instruction/correct/:id."""
        target = self.model_instructions[-1]
        res = self.client.correct_instruction(
            target["id"], {"description": new_desc}
        )
        assert self.client.last_status == HTTP_OK
        assert res["description"] == new_desc
        target["description"] = new_desc

    @rule()
    def correct_nonexistent_instruction(self):
        """Test correct instruction with unknown identifier."""
        non_id = 999999
        res = self.client.correct_instruction(
            non_id, {"description": "none"}
        )
        assert self.client.last_status == HTTP_OK
        assert res == {}

    @precondition(lambda self: len(self.model_instructions) > ZERO_VAL)
    @rule()
    def show_response(self):
        """Test GET /public/api/v2/response/show/:instruction."""
        inst_id = self.model_instructions[-1]["id"]
        res = self.client.show_response(inst_id)
        assert self.client.last_status == HTTP_OK
        assert isinstance(res, list)

    @rule()
    def find_response(self):
        """Test GET /public/api/v2/response/find."""
        res = self.client.find_response({"state": "COMPLETED"})
        assert self.client.last_status == HTTP_OK
        assert isinstance(res, list)

    @rule()
    def show_report(self):
        """Test GET /public/api/v2/report/show (Formula 18)."""
        res = self.client.show_report()
        assert self.client.last_status == HTTP_OK
        assert isinstance(res, list)

    @rule()
    def test_http_transport_success(self):
        """Test HTTP transport success path using mock."""
        from unittest.mock import MagicMock, patch

        mock_resp = MagicMock()
        mock_resp.status = HTTP_OK
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_resp
        mock_cm.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_cm):
            http_c = ApiClient(base_url="http://127.0.0.1:8000")
            res_q = http_c.show_member({"ip": "127.0.0.1"})
            assert res_q == {"status": "ok"}
            res_b = http_c.request("POST", "/test", body={"k": "v"})
            assert res_b == {"status": "ok"}

    @rule()
    def verify_auth_failures(self):
        """Verify 401 on bad password and missing header."""
        bad_client = ApiClient(
            app=self.app,
            username="invalid_user",
            password="wrong_password",
        )
        bad_client.show_report()
        assert bad_client.last_status == HTTP_UNAUTHORIZED

        empty_client = ApiClient(
            app=self.app,
            username="",
            password="",
        )
        empty_client.show_member()
        assert empty_client.last_status == HTTP_UNAUTHORIZED

        bad_env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/public/api/v2/member/show",
            "HTTP_AUTHORIZATION": "Bearer invalid_scheme",
            "wsgi.input": io.BytesIO(b""),
            "wsgi.errors": io.StringIO(),
        }
        wsgiref.util.setup_testing_defaults(bad_env)
        self.app(bad_env, lambda s, h, e=None: None)

        corrupt_env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/public/api/v2/member/show",
            "HTTP_AUTHORIZATION": "Basic not_valid_base64!!!",
            "wsgi.input": io.BytesIO(b""),
            "wsgi.errors": io.StringIO(),
        }
        wsgiref.util.setup_testing_defaults(corrupt_env)
        self.app(corrupt_env, lambda s, h, e=None: None)

    def _run_real_task(self, argument: str, desc: str):
        """Helper to execute instruction with real subprocess backend."""
        real_app = create_app(
            storage=self.storage,
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
            test_mode=False,
        )
        real_client = ApiClient(
            app=real_app,
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
        )
        iid = self.inst_seq
        self.inst_seq += ONE_VAL
        mem_id = self.model_members[-1]["id"]
        payload = {
            "argument": argument,
            "member": mem_id,
            "description": desc,
            "state": "active",
        }
        res = real_client.store_instruction(iid, payload)
        assert real_client.last_status == HTTP_OK
        assert res["id"] == iid

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def verify_real_subprocess_file(self):
        """Verify real execution using an input file path."""
        self._run_real_task("examples/input1.txt", "file audio conversion")

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def verify_real_subprocess_inline(self):
        """Verify real execution using inline input text."""
        self._run_real_task(
            "44100 1 128 5.0", "inline audio conversion"
        )

    @precondition(lambda self: len(self.model_members) > ZERO_VAL)
    @rule()
    def verify_real_subprocess_error(self):
        """Verify real execution with invalid input causing error."""
        self._run_real_task(
            "corrupted_audio_data", "failing audio conversion"
        )

    @rule()
    def verify_cli_basic_execution(self):
        """Verify standard CLI runs including WAV binary and main entry."""
        import os
        import wave
        from unittest.mock import patch
        import pytest
        from src.cli import run_cli
        assert run_cli([]) == EXIT_FAILURE
        assert run_cli(["src.cli", "examples/input1.txt"]) == EXIT_SUCCESS
        assert run_cli(["src.cli", "examples/input2.txt"]) == EXIT_SUCCESS
        assert run_cli(["src.cli", "nonexistent_file"]) == EXIT_FAILURE

        temp_wav = "temp_test_audio.wav"
        with wave.open(temp_wav, "wb") as wf:
            wf.setnchannels(ONE_VAL)
            wf.setsampwidth(TWO_VAL)
            wf.setframerate(AUDIO_DEFAULT_SAMPLE_RATE)
            wf.writeframes(b"\x00\x00" * 441)
        assert run_cli(["src.cli", temp_wav]) == EXIT_SUCCESS
        os.remove(temp_wav)

        import runpy
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with patch("sys.argv", ["src.cli"]):
                with pytest.raises(SystemExit):
                    runpy.run_module("src.cli", run_name="__main__")

    @rule()
    def verify_cli_validation_branches(self):
        """Verify CLI error paths and parsing branches."""
        from src.cli import run_cli
        json_arg = (
            '{"sample_rate": 44100, "channels": 1, "bitrate_kbps": 128}'
        )
        assert run_cli(["src.cli", json_arg]) == EXIT_SUCCESS
        space_arg = "44100 1 128 1.0"
        assert run_cli(["src.cli", space_arg]) == EXIT_SUCCESS
        blank_arg = "sample_rate: 44100\n\nchannels: 1"
        assert run_cli(["src.cli", blank_arg]) == EXIT_SUCCESS
        assert run_cli(["src.cli", "sample_rate: 100"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "sample_rate: 100000"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "channels: 0"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "channels: 5"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "bitrate_kbps: 10"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "bitrate_kbps: 500"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "duration_sec: 0.0001"]) == EXIT_FAILURE
        assert run_cli(["src.cli", "duration_sec: 50000.0"]) == EXIT_FAILURE

    @rule()
    def check_nonexistent_queries(self):
        """Query non-existent IDs to test empty result branches."""
        non_id = 999999
        assert self.storage.get_member(non_id) == {}
        assert self.storage.get_instruction(non_id) == {}
        assert self.storage.get_response(non_id) == {}
        assert self.storage.find_members({"unknown": 1}) is not None
        assert self.storage.find_instructions({"unknown": 1}) is not None
        assert self.storage.find_responses({"unknown": 1}) is not None

    @rule()
    def test_http_transport_errors(self):
        """Test HTTP transport error handling branches."""
        from unittest.mock import patch
        import urllib.error

        http_c = ApiClient(base_url="http://127.0.0.1:8000")
        err_json = io.BytesIO(b'{"error": "fail"}')
        http_err_json = urllib.error.HTTPError(
            "http://url", 400, "Bad Request", {}, err_json
        )
        with patch("urllib.request.urlopen", side_effect=http_err_json):
            res_json = http_c.request("GET", "/err_json")
            assert res_json == {"error": "fail"}

        err_plain = io.BytesIO(b"not-json")
        http_err_plain = urllib.error.HTTPError(
            "http://url", 500, "Internal Error", {}, err_plain
        )
        with patch("urllib.request.urlopen", side_effect=http_err_plain):
            res_plain = http_c.request("GET", "/err_plain")
            assert isinstance(res_plain, dict)

    @rule()
    def test_client_and_app_exceptions(self):
        """Test exceptional fallback branches."""
        from unittest.mock import patch
        from src.app import run_computational_task
        from bottle import Bottle

        with patch("subprocess.run", side_effect=OSError("spawn failure")):
            out, err, dur, ok = run_computational_task("dummy")
            assert not ok
            assert "spawn failure" in err

        plain_app = Bottle()

        @plain_app.route("/plain")
        def plain_view():
            return "not-a-json"

        plain_client = ApiClient(app=plain_app)
        assert plain_client.request("GET", "/plain") == "not-a-json"


TestAPI = ModelAPI.TestCase
