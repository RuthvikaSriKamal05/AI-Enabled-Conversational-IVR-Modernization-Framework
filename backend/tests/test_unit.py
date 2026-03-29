# =============================================================================
# tests/test_unit.py
# MILESTONE 4 — UNIT TESTS  (maps to backend/main.py)
#
# Tests the smallest logical units in total isolation:
#   • detect_intent()  — pure function, no HTTP
#   • POST /ivr/start  — session creation contract
#   • POST /ivr/input  — Pydantic validation layer
#   • STATIONS / TRAINS / MAIN_MENU constants
#
# Every test must complete in < 100 ms.
# External calls (DB, network) are never made — TestClient is fake HTTP.
# =============================================================================

import pytest
from fastapi.testclient import TestClient
from main import app, detect_intent, STATIONS, TRAINS, MAIN_MENU, sessions

client = TestClient(app)


# =============================================================================
# detect_intent() — pure function tests
# One test per keyword/alias from the actual if-blocks in main.py
# =============================================================================

class TestDetectIntent:

    # ── book_ticket ──────────────────────────────────────────────────────────
    def test_digit_1(self):          assert detect_intent("1")              == "book_ticket"
    def test_word_book(self):        assert detect_intent("book")           == "book_ticket"
    def test_word_ticket(self):      assert detect_intent("ticket")         == "book_ticket"
    def test_phrase_book_ticket(self):     assert detect_intent("book ticket")     == "book_ticket"
    def test_phrase_book_a_ticket(self):   assert detect_intent("book a ticket")   == "book_ticket"
    def test_word_general(self):     assert detect_intent("general")        == "book_ticket"
    def test_word_tatkal(self):      assert detect_intent("tatkal")         == "book_ticket"

    # ── pnr_status ───────────────────────────────────────────────────────────
    def test_digit_2(self):          assert detect_intent("2")              == "pnr_status"
    def test_word_pnr(self):         assert detect_intent("pnr")            == "pnr_status"
    def test_phrase_pnr_status(self):      assert detect_intent("pnr status")      == "pnr_status"
    def test_phrase_check_pnr(self):       assert detect_intent("check pnr")       == "pnr_status"

    # ── cancel_ticket ─────────────────────────────────────────────────────────
    def test_digit_3(self):          assert detect_intent("3")              == "cancel_ticket"
    def test_word_cancel(self):      assert detect_intent("cancel")         == "cancel_ticket"
    def test_phrase_cancel_ticket(self):   assert detect_intent("cancel ticket")   == "cancel_ticket"

    # ── train_schedule ────────────────────────────────────────────────────────
    def test_digit_4(self):          assert detect_intent("4")              == "train_schedule"
    def test_word_schedule(self):    assert detect_intent("schedule")       == "train_schedule"
    def test_phrase_train_schedule(self):  assert detect_intent("train schedule")  == "train_schedule"
    def test_word_train(self):       assert detect_intent("train")          == "train_schedule"

    # ── seat_availability ────────────────────────────────────────────────────
    def test_digit_5(self):          assert detect_intent("5")              == "seat_availability"
    def test_word_seat(self):        assert detect_intent("seat")           == "seat_availability"
    def test_phrase_seat_availability(self): assert detect_intent("seat availability") == "seat_availability"
    def test_word_availability(self):assert detect_intent("availability")   == "seat_availability"

    # ── agent ─────────────────────────────────────────────────────────────────
    def test_digit_9(self):          assert detect_intent("9")              == "agent"
    def test_word_agent(self):       assert detect_intent("agent")          == "agent"
    def test_phrase_customer_care(self):   assert detect_intent("customer care")   == "agent"

    # ── None (unrecognised) ───────────────────────────────────────────────────
    def test_garbage_input(self):    assert detect_intent("xyz_garbage")    is None
    def test_empty_string(self):     assert detect_intent("")               is None
    def test_digit_6_unknown(self):  assert detect_intent("6")              is None
    def test_digit_7_unknown(self):  assert detect_intent("7")              is None
    def test_digit_8_unknown(self):  assert detect_intent("8")              is None

    # ── case insensitivity ───────────────────────────────────────────────────
    def test_uppercase_book(self):   assert detect_intent("BOOK")           == "book_ticket"
    def test_uppercase_pnr(self):    assert detect_intent("PNR")            == "pnr_status"
    def test_mixed_case_cancel(self):assert detect_intent("Cancel Ticket")  == "cancel_ticket"

    # ── leading/trailing whitespace (strip) ───────────────────────────────────
    def test_whitespace_around_1(self):    assert detect_intent("  1  ")    == "book_ticket"
    def test_whitespace_around_pnr(self):  assert detect_intent("  pnr  ")  == "pnr_status"


# =============================================================================
# POST /ivr/start  — session creation contract
# =============================================================================

class TestStartCall:

    def test_returns_200(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        assert r.status_code == 200

    def test_returns_session_id(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        assert "session_id" in r.json()

    def test_session_id_starts_with_SIM_(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        assert r.json()["session_id"].startswith("SIM_")

    def test_returns_prompt(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        assert "prompt" in r.json()

    def test_prompt_is_main_menu(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        assert r.json()["prompt"] == MAIN_MENU

    def test_prompt_contains_all_option_numbers(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        p = r.json()["prompt"]
        for n in ["1", "2", "3", "4", "5", "9"]:
            assert n in p, f"Option {n} missing from main menu"

    def test_session_stored_in_sessions_dict(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        sid = r.json()["session_id"]
        assert sid in sessions

    def test_new_session_stage_is_main(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        sid = r.json()["session_id"]
        assert sessions[sid]["stage"] == "main"

    def test_new_session_intent_is_none(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        sid = r.json()["session_id"]
        assert sessions[sid]["intent"] is None

    def test_new_session_data_is_empty(self):
        r = client.post("/ivr/start", json={"caller_number": "9999999999"})
        sid = r.json()["session_id"]
        assert sessions[sid]["data"] == {}

    def test_two_calls_produce_unique_session_ids(self):
        r1 = client.post("/ivr/start", json={"caller_number": "1111111111"})
        r2 = client.post("/ivr/start", json={"caller_number": "2222222222"})
        assert r1.json()["session_id"] != r2.json()["session_id"]

    def test_missing_caller_number_returns_422(self):
        r = client.post("/ivr/start", json={})
        assert r.status_code == 422

    def test_wrong_field_name_returns_422(self):
        r = client.post("/ivr/start", json={"phone": "9999999999"})
        assert r.status_code == 422

    def test_422_contains_field_detail(self):
        r = client.post("/ivr/start", json={})
        assert "detail" in r.json()


# =============================================================================
# POST /ivr/input  — Pydantic validation & dead-session guard
# =============================================================================

class TestInputValidation:

    def test_missing_session_id_returns_422(self):
        r = client.post("/ivr/input", json={"value": "1"})
        assert r.status_code == 422

    def test_missing_value_returns_422(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_000001"})
        assert r.status_code == 422

    def test_empty_body_returns_422(self):
        r = client.post("/ivr/input", json={})
        assert r.status_code == 422

    def test_dead_session_returns_200_not_500(self):
        """Expired session must be handled gracefully — no server crash."""
        r = client.post("/ivr/input", json={"session_id": "SIM_GHOST", "value": "1"})
        assert r.status_code == 200

    def test_dead_session_returns_hangup(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GHOST", "value": "1"})
        assert r.json()["action"] == "hangup"

    def test_dead_session_prompt_is_human_readable(self):
        r = client.post("/ivr/input", json={"session_id": "SIM_GHOST", "value": "1"})
        prompt = r.json()["prompt"]
        assert "Session expired" in prompt
        assert "Traceback" not in prompt
        assert "KeyError" not in prompt

    def test_invalid_main_menu_digit_returns_error_prompt(self):
        start = client.post("/ivr/start", json={"caller_number": "9000000001"})
        sid = start.json()["session_id"]
        r = client.post("/ivr/input", json={"session_id": sid, "value": "7"})
        assert "Invalid" in r.json()["prompt"]

    def test_invalid_main_menu_does_not_hang_up(self):
        start = client.post("/ivr/start", json={"caller_number": "9000000002"})
        sid = start.json()["session_id"]
        r = client.post("/ivr/input", json={"session_id": sid, "value": "7"})
        assert r.json().get("action") != "hangup"


# =============================================================================
# Constants integrity
# =============================================================================

class TestConstants:

    def test_stations_has_9_entries(self):
        assert len(STATIONS) == 9

    def test_stations_keys_are_1_to_9(self):
        assert set(STATIONS.keys()) == {"1","2","3","4","5","6","7","8","9"}

    def test_stations_hyderabad_is_key_1(self):
        assert STATIONS["1"] == "Hyderabad Deccan"

    def test_stations_chennai_is_key_2(self):
        assert STATIONS["2"] == "Chennai Central"

    def test_stations_delhi_is_key_3(self):
        assert STATIONS["3"] == "New Delhi"

    def test_trains_has_3_entries(self):
        assert len(TRAINS) == 3

    def test_trains_contains_karnataka(self):
        assert any("Karnataka" in t for t in TRAINS)

    def test_trains_contains_charminar(self):
        assert any("Charminar" in t for t in TRAINS)

    def test_trains_contains_coromandel(self):
        assert any("Coromandel" in t for t in TRAINS)

    def test_main_menu_contains_welcome(self):
        assert "Welcome to IRCTC" in MAIN_MENU

    def test_main_menu_contains_all_press_options(self):
        for n in ["Press 1","Press 2","Press 3","Press 4","Press 5","Press 9"]:
            assert n in MAIN_MENU, f"'{n}' missing from MAIN_MENU"
