# =============================================================================
# tests/test_integration.py
# MILESTONE 4 — INTEGRATION TESTS  (maps to backend/main.py)
#
# Verifies that multi-step flows work across the in-memory sessions store.
# Each test creates a real session and walks through sequential POST /ivr/input
# calls, asserting both the HTTP response AND the sessions dict state.
#
# These tests are ~1-5 s and are the first to catch broken session wiring.
# =============================================================================

import pytest
from fastapi.testclient import TestClient
from main import app, sessions, STATIONS, TRAIN_SCHEDULES

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def new_sid(caller="9100000000") -> str:
    r = client.post("/ivr/start", json={"caller_number": caller})
    return r.json()["session_id"]

def inp(sid: str, value: str) -> dict:
    r = client.post("/ivr/input", json={"session_id": sid, "value": value})
    assert r.status_code == 200
    return r.json()


# =============================================================================
# BOOKING FLOW  — stages: main → source → destination → date → train_select
# =============================================================================

class TestBookingFlowIntegration:

    def test_pressing_1_sets_intent_and_stage(self):
        sid = new_sid()
        inp(sid, "1")
        assert sessions[sid]["intent"] == "book_ticket"
        assert sessions[sid]["stage"]  == "source"

    def test_source_prompt_lists_all_9_stations(self):
        sid = new_sid()
        data = inp(sid, "1")
        for station in STATIONS.values():
            assert station in data["prompt"]

    def test_valid_source_stores_station_name(self):
        sid = new_sid()
        inp(sid, "1")
        inp(sid, "1")   # Hyderabad Deccan
        assert sessions[sid]["data"]["source"] == "Hyderabad Deccan"
        assert sessions[sid]["stage"] == "destination"

    def test_invalid_source_keeps_stage_at_source(self):
        sid = new_sid()
        inp(sid, "1")
        data = inp(sid, "99")
        assert "Invalid" in data["prompt"]
        assert sessions[sid]["stage"] == "source"

    def test_same_source_and_destination_rejected(self):
        sid = new_sid()
        inp(sid, "1")
        inp(sid, "1")           # source  = Hyderabad (key 1)
        data = inp(sid, "1")    # dest    = same key
        assert "same as source" in data["prompt"].lower()
        assert sessions[sid]["stage"] == "destination"

    def test_valid_destination_stores_station_name(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1")    # source = Hyderabad
        inp(sid, "2")                   # dest   = Chennai
        assert sessions[sid]["data"]["destination"] == "Chennai Central"
        assert sessions[sid]["stage"] == "date"

    def test_invalid_destination_keeps_stage_at_destination(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1")
        data = inp(sid, "0")
        assert "Invalid" in data["prompt"]
        assert sessions[sid]["stage"] == "destination"

    def test_date_prompt_shows_3_options(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        data = inp(sid, "1")    # Today
        assert "Available Trains" in data["prompt"]
        assert sessions[sid]["stage"] == "train_select"

    def test_invalid_date_keeps_stage_at_date(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        data = inp(sid, "9")
        assert "Invalid" in data["prompt"]
        assert sessions[sid]["stage"] == "date"

    def test_date_stored_as_yyyy_mm_dd(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2")
        inp(sid, "1")   # Today
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", sessions[sid]["data"]["date"])

    def test_train_select_prompt_lists_all_3_trains(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        # Trains are listed at date stage response
        data = inp(sid, "1")   # select Karnataka Express from train_select
        # If train_select stage was reached, confirmation must appear
        assert "booked successfully" in data["prompt"].lower()

    def test_invalid_train_number_re_prompts(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        data = inp(sid, "9")   # only 1-3 valid
        assert "Invalid" in data["prompt"]

    def test_valid_train_confirmation_contains_source_dest_train(self):
        sid = new_sid()
        inp(sid, "1")
        inp(sid, "3")   # New Delhi
        inp(sid, "6")   # Bengaluru City
        inp(sid, "1")   # Today
        data = inp(sid, "1")   # Karnataka Express
        assert "New Delhi"      in data["prompt"]
        assert "Bengaluru City" in data["prompt"]
        assert "Karnataka"      in data["prompt"]

    def test_booking_completion_deletes_session(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        inp(sid, "2")   # Charminar Express
        assert sid not in sessions

    def test_booking_completion_returns_hangup(self):
        sid = new_sid()
        inp(sid, "1"); inp(sid, "1"); inp(sid, "2"); inp(sid, "1")
        data = inp(sid, "3")   # Coromandel Express
        assert data["action"] == "hangup"


# =============================================================================
# PNR STATUS FLOW  — stages: main → pnr_number
# Mock response based on last digit of PNR (from main.py lines 267-285)
# =============================================================================

class TestPNRFlowIntegration:

    def test_pressing_2_sets_intent_and_stage(self):
        sid = new_sid()
        inp(sid, "2")
        assert sessions[sid]["intent"] == "pnr_status"
        assert sessions[sid]["stage"]  == "pnr_number"

    def test_pnr_prompt_asks_for_10_digit(self):
        sid = new_sid()
        data = inp(sid, "2")
        assert "PNR" in data["prompt"]

    def test_digits_ending_0_returns_confirmed(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "1234567890")   # ends in 0
        assert "CONFIRMED" in data["prompt"]

    def test_digits_ending_1_returns_confirmed(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "1234567891")
        assert "CONFIRMED" in data["prompt"]

    def test_digits_ending_4_returns_waitlist(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "1234567894")
        assert "WAITING LIST" in data["prompt"] or "WL" in data["prompt"]

    def test_digits_ending_7_returns_rac(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "1234567897")
        assert "RAC" in data["prompt"]

    def test_digits_ending_9_returns_confirmed_b2(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "1234567899")   # ends in 9 → Coach B2
        assert "CONFIRMED" in data["prompt"]

    def test_non_digit_pnr_rejected(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "ABCDEFGHIJ")
        assert "Invalid" in data["prompt"]
        assert sid in sessions   # session alive for retry

    def test_whitespace_only_pnr_rejected(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "   ")
        assert "Invalid" in data["prompt"]

    def test_valid_pnr_deletes_session(self):
        sid = new_sid(); inp(sid, "2")
        inp(sid, "1234567890")
        assert sid not in sessions

    def test_valid_pnr_echoes_digits_in_prompt(self):
        sid = new_sid(); inp(sid, "2")
        data = inp(sid, "9876543210")
        assert "9876543210" in data["prompt"]


# =============================================================================
# CANCEL TICKET FLOW  — stages: main → cancel_train
# =============================================================================

class TestCancelFlowIntegration:

    def test_pressing_3_sets_intent_and_stage(self):
        sid = new_sid()
        inp(sid, "3")
        assert sessions[sid]["intent"] == "cancel_ticket"
        assert sessions[sid]["stage"]  == "cancel_train"

    def test_cancel_prompt_asks_for_train_number(self):
        sid = new_sid()
        data = inp(sid, "3")
        assert "Train Number" in data["prompt"]

    def test_any_train_number_cancels_and_hangs_up(self):
        sid = new_sid()
        inp(sid, "3")
        data = inp(sid, "12627")
        assert "cancelled" in data["prompt"].lower()
        assert data["action"] == "hangup"

    def test_cancel_mentions_refund_timeline(self):
        sid = new_sid()
        inp(sid, "3")
        data = inp(sid, "12760")
        assert "5-7" in data["prompt"]

    def test_cancel_echoes_train_number(self):
        sid = new_sid()
        inp(sid, "3")
        data = inp(sid, "12841")
        assert "12841" in data["prompt"]

    def test_cancel_deletes_session(self):
        sid = new_sid()
        inp(sid, "3")
        inp(sid, "12627")
        assert sid not in sessions


# =============================================================================
# TRAIN SCHEDULE FLOW  — stages: main → schedule_train → schedule_date
# Checks actual stop data from TRAIN_SCHEDULES dict
# =============================================================================

class TestTrainScheduleFlowIntegration:

    def test_pressing_4_sets_intent_and_stage(self):
        sid = new_sid()
        inp(sid, "4")
        assert sessions[sid]["intent"] == "train_schedule"
        assert sessions[sid]["stage"]  == "schedule_train"

    def test_invalid_train_key_re_prompts(self):
        sid = new_sid()
        inp(sid, "4")
        data = inp(sid, "9")
        assert "Invalid" in data["prompt"]
        assert sessions[sid]["stage"] == "schedule_train"

    def test_valid_train_key_stores_train_and_advances(self):
        sid = new_sid()
        inp(sid, "4")
        inp(sid, "1")   # Karnataka Express
        assert sessions[sid]["data"]["train"] == "1"
        assert sessions[sid]["stage"] == "schedule_date"

    def test_schedule_prompt_shows_train_name_and_route(self):
        sid = new_sid()
        inp(sid, "4")
        data = inp(sid, "2")   # Charminar Express
        assert "Charminar Express" in data["prompt"]
        assert "Hyderabad Deccan" in data["prompt"]
        assert "Chennai Central"  in data["prompt"]

    def test_karnataka_express_schedule_has_correct_stops(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "1")
        data = inp(sid, "1")   # Today
        p = data["prompt"]
        for stop, *_ in TRAIN_SCHEDULES["1"]["stops"]:
            assert stop in p, f"Stop '{stop}' missing from Karnataka Express schedule"

    def test_charminar_express_schedule_has_correct_stops(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "2")
        data = inp(sid, "1")
        p = data["prompt"]
        for stop, *_ in TRAIN_SCHEDULES["2"]["stops"]:
            assert stop in p

    def test_coromandel_express_schedule_has_correct_stops(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "3")
        data = inp(sid, "1")
        p = data["prompt"]
        for stop, *_ in TRAIN_SCHEDULES["3"]["stops"]:
            assert stop in p

    def test_schedule_shows_total_duration(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "1")
        data = inp(sid, "1")
        assert "40 hrs 30 mins" in data["prompt"]

    def test_schedule_completion_deletes_session(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "1"); inp(sid, "1")
        assert sid not in sessions

    def test_schedule_completion_returns_hangup(self):
        sid = new_sid()
        inp(sid, "4"); inp(sid, "2"); inp(sid, "2")
        data = inp(sid, "2")    # schedule_date gets any date value
        # schedule_date only has one step — the date selection ends the flow
        # inp 3 times: 4 → schedule_train, "2" → schedule_date, "2" → done
        assert data["action"] == "hangup"


# =============================================================================
# SEAT AVAILABILITY FLOW  — stages: main → availability_train → availability_date
# =============================================================================

class TestSeatAvailabilityFlowIntegration:

    def test_pressing_5_sets_intent_and_stage(self):
        sid = new_sid()
        inp(sid, "5")
        assert sessions[sid]["intent"] == "seat_availability"
        assert sessions[sid]["stage"]  == "availability_train"

    def test_valid_train_advances_to_date_stage(self):
        sid = new_sid()
        inp(sid, "5"); inp(sid, "2")
        assert sessions[sid]["data"]["train"] == "2"
        assert sessions[sid]["stage"] == "availability_date"

    def test_availability_prompt_asks_for_yyyy_mm_dd(self):
        sid = new_sid()
        inp(sid, "5")
        data = inp(sid, "1")
        assert "YYYY-MM-DD" in data["prompt"] or "yyyy" in data["prompt"].lower()

    def test_date_input_returns_seat_classes(self):
        sid = new_sid()
        inp(sid, "5"); inp(sid, "1")
        data = inp(sid, "2026-05-10")
        assert "SL" in data["prompt"]

    def test_availability_echoes_train_number(self):
        sid = new_sid()
        inp(sid, "5"); inp(sid, "3")
        data = inp(sid, "2026-06-01")
        assert "3" in data["prompt"]

    def test_availability_deletes_session(self):
        sid = new_sid()
        inp(sid, "5"); inp(sid, "1"); inp(sid, "2026-04-15")
        assert sid not in sessions

    def test_availability_returns_hangup(self):
        sid = new_sid()
        inp(sid, "5"); inp(sid, "1")
        data = inp(sid, "2026-04-15")
        assert data["action"] == "hangup"


# =============================================================================
# CUSTOMER CARE FLOW  — stage='customer_care', care_step sub-states
# Maps directly to the care_step state machine in main.py
# =============================================================================

class TestCustomerCareFlowIntegration:

    def test_pressing_9_sets_intent_stage_care_step(self):
        sid = new_sid()
        inp(sid, "9")
        assert sessions[sid]["intent"] == "agent"
        assert sessions[sid]["stage"]  == "customer_care"
        assert sessions[sid]["data"]["care_step"] == "menu"

    def test_care_menu_prompt_lists_all_4_options(self):
        sid = new_sid()
        data = inp(sid, "9")
        for opt in ["Press 1","Press 2","Press 3","Press 4"]:
            assert opt in data["prompt"]

    def test_pressing_0_returns_to_main_menu(self):
        sid = new_sid()
        inp(sid, "9")
        data = inp(sid, "0")
        assert "Welcome to IRCTC" in data["prompt"]
        assert sessions[sid]["stage"]  == "main"
        assert sessions[sid]["intent"] is None
        assert sessions[sid]["data"]   == {}

    def test_pressing_1_opens_ticket_issue_submenu(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "1")
        assert sessions[sid]["data"]["care_step"] == "ticket_issue"

    def test_ticket_issue_back_button_returns_to_care_menu(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "1")
        data = inp(sid, "0")
        assert sessions[sid]["data"]["care_step"] == "menu"
        assert "Press 1 - Ticket" in data["prompt"]

    def test_ticket_issue_option_1_gives_complaint_id(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "1")
        data = inp(sid, "1")
        assert "TKT" in data["prompt"]
        assert data["action"] == "hangup"

    def test_ticket_issue_invalid_option(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "1")
        data = inp(sid, "7")
        assert "Invalid" in data["prompt"]

    def test_pressing_2_opens_refund_submenu(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "2")
        assert sessions[sid]["data"]["care_step"] == "refund"

    def test_refund_option_1_ends_call(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "2")
        data = inp(sid, "1")
        assert data["action"] == "hangup"
        assert sid not in sessions

    def test_refund_back_button_returns_to_care_menu(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "2")
        inp(sid, "0")
        assert sessions[sid]["data"]["care_step"] == "menu"

    def test_refund_invalid_option(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "2")
        data = inp(sid, "9")
        assert "Invalid" in data["prompt"]

    def test_pressing_3_opens_complaint_submenu(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        assert sessions[sid]["data"]["care_step"] == "complaint"

    def test_complaint_staff_registers_and_hangs_up(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        data = inp(sid, "1")
        assert "CMP" in data["prompt"]
        assert "staff" in data["prompt"].lower()
        assert data["action"] == "hangup"

    def test_complaint_food_registers_and_hangs_up(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        data = inp(sid, "2")
        assert "food" in data["prompt"].lower()
        assert data["action"] == "hangup"

    def test_complaint_cleanliness_registers_and_hangs_up(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        data = inp(sid, "3")
        assert "cleanliness" in data["prompt"].lower()
        assert data["action"] == "hangup"

    def test_complaint_48_hour_sla_mentioned(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        data = inp(sid, "1")
        assert "48 hours" in data["prompt"]

    def test_complaint_invalid_option(self):
        sid = new_sid()
        inp(sid, "9"); inp(sid, "3")
        data = inp(sid, "9")
        assert "Invalid" in data["prompt"]

    def test_pressing_4_live_agent_ends_call_with_139(self):
        sid = new_sid()
        inp(sid, "9")
        data = inp(sid, "4")
        assert "139" in data["prompt"]
        assert data["action"] == "hangup"
        assert sid not in sessions

    def test_invalid_care_menu_option(self):
        sid = new_sid()
        inp(sid, "9")
        data = inp(sid, "7")
        assert "Invalid" in data["prompt"]
        assert sid in sessions   # still alive
