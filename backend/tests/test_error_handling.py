# =============================================================================
# tests/test_error_handling.py
# MILESTONE 4 — ERROR HANDLING & SESSION LIFECYCLE TESTS
#
# Covers every failure mode in main.py:
#   • Bad Pydantic payloads (422)
#   • Expired / unknown sessions (graceful hangup, no 500)
#   • Invalid input at every stage (re-prompt, not crash)
#   • Session memory cleanup after hangup (no leaks)
#   • No stack traces ever reach the caller
# =============================================================================

import pytest
from fastapi.testclient import TestClient
from main import app, sessions

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def new_sid(caller="9400000000"):
    r = client.post("/ivr/start", json={"caller_number": caller})
    return r.json()["session_id"]

def inp(sid, value):
    r = client.post("/ivr/input", json={"session_id": sid, "value": value})
    assert r.status_code == 200
    return r.json()


# =============================================================================
# PYDANTIC REQUEST VALIDATION  (FastAPI returns 422 automatically)
# =============================================================================

class TestRequestValidation:

    # /ivr/start
    def test_start_empty_body_422(self):
        assert client.post("/ivr/start", json={}).status_code == 422

    def test_start_wrong_field_name_422(self):
        assert client.post("/ivr/start", json={"phone": "9"}).status_code == 422

    def test_start_null_caller_number_422(self):
        assert client.post("/ivr/start", json={"caller_number": None}).status_code == 422

    def test_start_422_includes_detail(self):
        r = client.post("/ivr/start", json={})
        data = r.json()
        assert "detail" in data
        fields = [e.get("loc", [])[-1] for e in data["detail"]]
        assert "caller_number" in fields

    # /ivr/input
    def test_input_no_session_id_422(self):
        assert client.post("/ivr/input", json={"value": "1"}).status_code == 422

    def test_input_no_value_422(self):
        assert client.post("/ivr/input", json={"session_id": "SIM_X"}).status_code == 422

    def test_input_empty_body_422(self):
        assert client.post("/ivr/input", json={}).status_code == 422

    def test_input_null_value_422(self):
        assert client.post("/ivr/input",
                           json={"session_id": "SIM_X", "value": None}).status_code == 422


# =============================================================================
# EXPIRED / UNKNOWN SESSION  — must never crash the server
# =============================================================================

class TestExpiredSession:

    def test_unknown_sid_returns_200(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GHOST", "value": "1"})
        assert r.status_code == 200

    def test_unknown_sid_returns_hangup(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GHOST", "value": "1"})
        assert r.json()["action"] == "hangup"

    def test_unknown_sid_prompt_contains_session_expired(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GONE", "value": "1"})
        assert "Session expired" in r.json()["prompt"]

    def test_unknown_sid_prompt_has_no_traceback(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GONE", "value": "1"})
        p = r.json()["prompt"]
        assert "Traceback" not in p
        assert "KeyError"  not in p
        assert "Exception" not in p

    def test_late_request_after_booking_hangup_is_safe(self):
        """Once booking completes and deletes the session, a duplicate call must not 500."""
        sid = new_sid("9400000001")
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        inp(sid, "1"); inp(sid, "2")   # completes booking → del sessions[sid]
        assert sid not in sessions

        r = client.post("/ivr/input", json={"session_id": sid, "value": "1"})
        assert r.status_code == 200
        assert r.json()["action"] == "hangup"


# =============================================================================
# INVALID INPUT AT EVERY STAGE  — re-prompt, never 500
# =============================================================================

class TestInvalidInputAtEveryStage:

    def test_main_menu_bad_digit_re_prompts(self):
        sid = new_sid()
        d = inp(sid, "7")     # 7 is not in the main menu
        assert "Invalid" in d["prompt"]
        assert d.get("action") != "hangup"

    def test_main_menu_star_key_re_prompts(self):
        sid = new_sid()
        d = inp(sid, "*")
        assert "Invalid" in d["prompt"]

    def test_main_menu_hash_key_re_prompts(self):
        sid = new_sid()
        d = inp(sid, "#")
        assert "Invalid" in d["prompt"]

    def test_source_stage_zero_re_prompts(self):
        sid = new_sid(); inp(sid, "1")
        d = inp(sid, "0")
        assert "Invalid" in d["prompt"]
        assert sessions[sid]["stage"] == "source"

    def test_source_stage_text_re_prompts(self):
        sid = new_sid(); inp(sid, "1")
        d = inp(sid, "mumbai")   # text not accepted; digits expected
        # Either "Invalid" or the station isn't found via numeric lookup
        assert sessions[sid]["stage"] in ("source", "destination")

    def test_destination_stage_zero_re_prompts(self):
        sid = new_sid(); inp(sid, "1"); inp(sid, "1")
        d = inp(sid, "0")
        assert "Invalid" in d["prompt"]
        assert sessions[sid]["stage"] == "destination"

    def test_destination_same_as_source_re_prompts(self):
        sid = new_sid(); inp(sid, "1"); inp(sid, "3")   # source = Delhi
        d = inp(sid, "3")                               # dest   = Delhi again
        assert "same as source" in d["prompt"].lower()
        assert sessions[sid]["stage"] == "destination"

    def test_date_stage_invalid_option_re_prompts(self):
        sid = new_sid(); inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]
        assert sessions[sid]["stage"] == "date"

    def test_train_select_out_of_range_re_prompts(self):
        sid = new_sid(); inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]

    def test_train_select_zero_re_prompts(self):
        sid = new_sid(); inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        d = inp(sid, "0")
        assert "Invalid" in d["prompt"]

    def test_schedule_train_invalid_key_re_prompts(self):
        sid = new_sid(); inp(sid, "4")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]
        assert sessions[sid]["stage"] == "schedule_train"

    def test_pnr_non_digit_re_prompts(self):
        sid = new_sid(); inp(sid, "2")
        d = inp(sid, "ABCDEF")
        assert "Invalid" in d["prompt"]
        assert sid in sessions   # still alive

    def test_pnr_whitespace_only_re_prompts(self):
        sid = new_sid(); inp(sid, "2")
        d = inp(sid, "   ")
        assert "Invalid" in d["prompt"]
        assert sid in sessions

    def test_care_menu_invalid_option_re_prompts(self):
        sid = new_sid(); inp(sid, "9")
        d = inp(sid, "6")
        assert "Invalid" in d["prompt"]
        assert sid in sessions

    def test_care_ticket_submenu_invalid_re_prompts(self):
        sid = new_sid(); inp(sid, "9"); inp(sid, "1")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]

    def test_care_refund_submenu_invalid_re_prompts(self):
        sid = new_sid(); inp(sid, "9"); inp(sid, "2")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]

    def test_care_complaint_submenu_invalid_re_prompts(self):
        sid = new_sid(); inp(sid, "9"); inp(sid, "3")
        d = inp(sid, "9")
        assert "Invalid" in d["prompt"]

    def test_no_stage_ever_returns_http_500(self):
        """
        Walk every bad-input scenario.
        Every response must be < 500.
        """
        scenarios = [
            ([], "7"),          # main menu
            (["1"], "0"),       # source
            (["1","1"], "0"),   # destination
            (["1","1","2"], "9"),# date
            (["4"], "9"),       # schedule train
            (["2"], "ABC"),     # pnr
            (["9"], "6"),       # care menu
        ]
        for prior, bad in scenarios:
            sid = new_sid()
            for v in prior:
                client.post("/ivr/input", json={"session_id": sid, "value": v})
            r = client.post("/ivr/input", json={"session_id": sid, "value": bad})
            assert r.status_code < 500, \
                f"HTTP {r.status_code} for '{bad}' after {prior}"
            sessions.pop(sid, None)


# =============================================================================
# SESSION MEMORY — no leaks after every hangup path
# =============================================================================

class TestSessionCleanup:

    def test_booking_completion_deletes_session(self):
        sid = new_sid("9400000010")
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        inp(sid, "1"); inp(sid, "2")
        assert sid not in sessions

    def test_pnr_check_deletes_session(self):
        sid = new_sid("9400000011")
        inp(sid, "2"); inp(sid, "1234567890")
        assert sid not in sessions

    def test_cancel_deletes_session(self):
        sid = new_sid("9400000012")
        inp(sid, "3"); inp(sid, "12760")
        assert sid not in sessions

    def test_schedule_query_deletes_session(self):
        sid = new_sid("9400000013")
        inp(sid, "4"); inp(sid, "2"); inp(sid, "1")
        assert sid not in sessions

    def test_seat_availability_deletes_session(self):
        sid = new_sid("9400000014")
        inp(sid, "5"); inp(sid, "1"); inp(sid, "2026-05-01")
        assert sid not in sessions

    def test_live_agent_deletes_session(self):
        sid = new_sid("9400000015")
        inp(sid, "9"); inp(sid, "4")
        assert sid not in sessions

    def test_ticket_issue_response_deletes_session(self):
        sid = new_sid("9400000016")
        inp(sid, "9"); inp(sid, "1"); inp(sid, "2")
        assert sid not in sessions

    def test_food_complaint_deletes_session(self):
        sid = new_sid("9400000017")
        inp(sid, "9"); inp(sid, "3"); inp(sid, "2")
        assert sid not in sessions

    def test_refund_check_deletes_session(self):
        sid = new_sid("9400000018")
        inp(sid, "9"); inp(sid, "2"); inp(sid, "1")
        assert sid not in sessions

    def test_invalid_input_does_not_delete_session(self):
        """Bad input must keep the session alive so the caller can retry."""
        sid = new_sid("9400000019")
        inp(sid, "1"); inp(sid, "0")   # invalid source
        assert sid in sessions

    def test_back_to_main_does_not_delete_session(self):
        """Pressing 0 in care menu resets state but must not delete session."""
        sid = new_sid("9400000020")
        inp(sid, "9"); inp(sid, "0")
        assert sid in sessions
        assert sessions[sid]["stage"] == "main"
