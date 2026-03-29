# =============================================================================
# tests/test_e2e.py
# MILESTONE 4 — END-TO-END TESTS  (maps to backend/main.py + frontend flow)
#
# Simulates the complete caller experience from POST /ivr/start to hangup.
# Each test is a USER STORY — it proves the entire IVR path works as a whole.
#
# These mirror exactly what the Web Simulator (script.js handleInput chain)
# and voice_ivr.py run() loop do in production.
# =============================================================================

import pytest
from fastapi.testclient import TestClient
from main import app, sessions

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers — mirrors voice_ivr.py start_call() and send_input()
# ---------------------------------------------------------------------------

def dial(caller="9200000000"):
    r = client.post("/ivr/start", json={"caller_number": caller})
    assert r.status_code == 200
    d = r.json()
    return d["session_id"], d["prompt"]

def press(sid, value):
    r = client.post("/ivr/input", json={"session_id": sid, "value": value})
    assert r.status_code == 200
    return r.json()


# =============================================================================
# HAPPY PATH — all 6 IVR journeys from dial-in to hangup
# =============================================================================

class TestBookingJourneys:
    """
    Story: 'As a caller, I want to book a train ticket.'
    Covers all three trains and all three date options.
    """

    def test_hyderabad_to_chennai_tomorrow_charminar(self):
        sid, prompt = dial("9200000001")

        # Main menu received
        assert "Welcome to IRCTC IVR System" in prompt
        assert "Press 1 for Ticket Booking" in prompt

        # Press 1 → source
        d = press(sid, "1")
        assert "Source Station" in d["prompt"]
        assert "Hyderabad Deccan" in d["prompt"]

        # Pick Hyderabad (1) → destination
        d = press(sid, "1")
        assert "Destination Station" in d["prompt"]

        # Pick Chennai (2) → date
        d = press(sid, "2")
        assert "Journey Date" in d["prompt"]

        # Tomorrow (2) → trains
        d = press(sid, "2")
        assert "Available Trains" in d["prompt"]
        assert "Charminar Express" in d["prompt"]

        # Pick Charminar (2) → confirmation
        d = press(sid, "2")
        assert "booked successfully" in d["prompt"].lower()
        assert "Hyderabad Deccan"    in d["prompt"]
        assert "Chennai Central"     in d["prompt"]
        assert "Charminar Express"   in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions

    def test_delhi_to_bengaluru_today_karnataka(self):
        sid, _ = dial("9200000002")
        press(sid, "1")           # Book ticket
        press(sid, "3")           # Source: New Delhi
        press(sid, "6")           # Dest:   Bengaluru City
        press(sid, "1")           # Date:   Today
        d = press(sid, "1")       # Train:  Karnataka Express
        assert "Karnataka Express" in d["prompt"]
        assert "New Delhi"         in d["prompt"]
        assert "Bengaluru City"    in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions

    def test_howrah_to_chennai_day_after_coromandel(self):
        sid, _ = dial("9200000003")
        press(sid, "1")
        press(sid, "5")           # Source: Howrah Junction
        press(sid, "2")           # Dest:   Chennai Central
        press(sid, "3")           # Date:   Day After Tomorrow
        d = press(sid, "3")       # Train:  Coromandel Express
        assert "Coromandel Express" in d["prompt"]
        assert "Howrah Junction"    in d["prompt"]
        assert "Chennai Central"    in d["prompt"]
        assert d["action"] == "hangup"

    def test_booking_date_stored_in_confirmation(self):
        """Confirmation prompt must include a date string."""
        import re
        sid, _ = dial("9200000004")
        press(sid, "1"); press(sid, "4")  # Mumbai CSMT
        press(sid, "9")                    # Ahmedabad
        press(sid, "1")                    # Today
        d = press(sid, "1")
        # Date should appear as YYYY-MM-DD somewhere in prompt
        assert re.search(r"\d{4}-\d{2}-\d{2}", d["prompt"])


class TestPNRJourneys:
    """Story: 'As a caller, I want to check my PNR status.'"""

    def test_confirmed_pnr_full_journey(self):
        sid, prompt = dial("9200000010")
        assert "Press 2 for PNR Status" in prompt

        d = press(sid, "2")
        assert "PNR" in d["prompt"]

        d = press(sid, "1234567890")   # ends in 0 → CONFIRMED
        assert "CONFIRMED" in d["prompt"]
        assert "Coach"     in d["prompt"]
        assert "Seat"      in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions

    def test_waitlist_pnr_full_journey(self):
        sid, _ = dial("9200000011")
        press(sid, "2")
        d = press(sid, "1234567894")   # ends in 4 → WAITING LIST
        assert "WAITING LIST" in d["prompt"] or "WL" in d["prompt"]
        assert d["action"] == "hangup"

    def test_rac_pnr_full_journey(self):
        sid, _ = dial("9200000012")
        press(sid, "2")
        d = press(sid, "1234567897")   # ends in 7 → RAC
        assert "RAC" in d["prompt"]
        assert d["action"] == "hangup"

    def test_pnr_retry_then_success(self):
        """Caller enters bad PNR first, then correct digits — must still work."""
        sid, _ = dial("9200000013")
        press(sid, "2")
        bad = press(sid, "BADPNR")     # rejected
        assert "Invalid" in bad["prompt"]
        assert sid in sessions          # still alive

        good = press(sid, "9876543211")
        assert "CONFIRMED" in good["prompt"]
        assert good["action"] == "hangup"


class TestCancelJourney:
    """Story: 'As a caller, I want to cancel my ticket.'"""

    def test_cancel_full_journey(self):
        sid, prompt = dial("9200000020")
        assert "Press 3 to Cancel Ticket" in prompt

        d = press(sid, "3")
        assert "Train Number" in d["prompt"]

        d = press(sid, "12760")   # Charminar Express
        assert "cancelled" in d["prompt"].lower()
        assert "Refund"    in d["prompt"]
        assert "5-7"       in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions


class TestScheduleJourneys:
    """Story: 'As a caller, I want to hear the train schedule.'"""

    def test_karnataka_express_schedule_full_journey(self):
        sid, prompt = dial("9200000030")
        assert "Press 4 for Train Schedule" in prompt

        d = press(sid, "4")
        assert "Karnataka" in d["prompt"]

        d = press(sid, "1")   # Karnataka Express
        assert "Karnataka Express" in d["prompt"]
        assert "New Delhi"         in d["prompt"]
        assert "Bengaluru City"    in d["prompt"]
        assert "40 hrs 30 mins"    in d["prompt"]

        d = press(sid, "1")   # Today
        # All stops must appear in the schedule output
        for stop in ["New Delhi","Mathura Junction","Agra Cantt","Gwalior",
                     "Jhansi","Bhopal","Nagpur","Secunderabad","Bengaluru City"]:
            assert stop in d["prompt"], f"Stop '{stop}' missing"
        assert d["action"] == "hangup"
        assert sid not in sessions

    def test_charminar_express_schedule_full_journey(self):
        sid, _ = dial("9200000031")
        press(sid, "4"); press(sid, "2")
        d = press(sid, "2")   # Tomorrow
        for stop in ["Hyderabad Deccan","Secunderabad","Warangal",
                     "Vijayawada","Gudur","Nellore","Chennai Central"]:
            assert stop in d["prompt"]
        assert "13 hrs 5 mins" in d["prompt"]
        assert d["action"] == "hangup"

    def test_coromandel_express_schedule_full_journey(self):
        sid, _ = dial("9200000032")
        press(sid, "4"); press(sid, "3")
        d = press(sid, "3")   # Day after tomorrow
        for stop in ["Howrah Junction","Kharagpur","Bhubaneswar",
                     "Visakhapatnam","Vijayawada","Nellore","Chennai Central"]:
            assert stop in d["prompt"]
        assert "26 hrs 30 mins" in d["prompt"]
        assert d["action"] == "hangup"


class TestSeatAvailabilityJourney:
    """Story: 'As a caller, I want to check seat availability.'"""

    def test_seat_availability_full_journey(self):
        sid, prompt = dial("9200000040")
        assert "Press 5 to Check Seat Availability" in prompt

        d = press(sid, "5")
        d = press(sid, "2")            # train 2
        assert "YYYY-MM-DD" in d["prompt"] or "yyyy" in d["prompt"].lower()

        d = press(sid, "2026-04-20")
        assert "SL" in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions


class TestCustomerCareJourneys:
    """Story: 'As a caller, I want to reach customer care.'"""

    def test_live_agent_journey(self):
        sid, prompt = dial("9200000050")
        assert "Press 9 to Talk to Customer Care" in prompt

        d = press(sid, "9")
        assert "Customer Care" in d["prompt"] or "Connecting" in d["prompt"]
        assert "Press 1" in d["prompt"]

        d = press(sid, "4")   # Live agent
        assert "139"        in d["prompt"]
        assert d["action"] == "hangup"
        assert sid not in sessions

    def test_food_complaint_full_journey(self):
        sid, _ = dial("9200000051")
        press(sid, "9")
        press(sid, "3")    # Complaint registration
        d = press(sid, "2")  # Food quality
        assert "CMP"        in d["prompt"]
        assert "food"       in d["prompt"].lower()
        assert "48 hours"   in d["prompt"]
        assert d["action"] == "hangup"

    def test_staff_complaint_full_journey(self):
        sid, _ = dial("9200000052")
        press(sid, "9"); press(sid, "3")
        d = press(sid, "1")
        assert "staff" in d["prompt"].lower()
        assert "CMP"   in d["prompt"]

    def test_ticket_issue_amount_deducted(self):
        sid, _ = dial("9200000053")
        press(sid, "9"); press(sid, "1")
        d = press(sid, "1")
        assert "TKT"         in d["prompt"]
        assert "Refund"      in d["prompt"]
        assert d["action"] == "hangup"

    def test_refund_status_journey(self):
        sid, _ = dial("9200000054")
        press(sid, "9"); press(sid, "2")
        d = press(sid, "1")
        assert "refund"     in d["prompt"].lower()
        assert d["action"] == "hangup"


# =============================================================================
# EDGE CASE JOURNEYS
# =============================================================================

class TestEdgeCaseJourneys:

    def test_back_to_main_then_full_booking(self):
        """
        Caller goes to care, presses 0 (back to main), then completes a booking.
        Tests that session reset via 'Press 0' doesn't break subsequent flows.
        """
        sid, _ = dial("9200000060")
        press(sid, "9")      # Enter care
        press(sid, "0")      # Back to main menu
        assert sessions[sid]["stage"]  == "main"
        assert sessions[sid]["intent"] is None

        # Now do a full booking
        press(sid, "1"); press(sid, "6")  # Bengaluru
        press(sid, "5")                    # Howrah
        press(sid, "1")                    # Today
        d = press(sid, "3")               # Coromandel
        assert "booked successfully" in d["prompt"].lower()
        assert d["action"] == "hangup"

    def test_two_callers_do_not_share_session_state(self):
        """
        Caller A books a ticket; Caller B checks PNR.
        Their sessions must never bleed into each other.
        """
        sid_a, _ = dial("9200000061")
        sid_b, _ = dial("9200000062")

        press(sid_a, "1"); press(sid_a, "3")  # A: booking, source = Delhi
        press(sid_b, "2")                      # B: PNR check

        # A's state untouched by B's actions
        assert sessions[sid_a]["intent"] == "book_ticket"
        assert sessions[sid_a]["stage"]  == "destination"
        assert sessions[sid_a]["data"]["source"] == "New Delhi"

        # B's state untouched by A's actions
        assert sessions[sid_b]["intent"] == "pnr_status"
        assert sessions[sid_b]["stage"]  == "pnr_number"

        # Cleanup
        sessions.pop(sid_a, None)
        sessions.pop(sid_b, None)

    def test_repeated_invalid_inputs_never_crash_server(self):
        """Pressing unknown keys multiple times must never return 5xx."""
        sid, _ = dial("9200000063")
        for bad in ["0", "6", "7", "8", "#", "*", "xyz", ""]:
            r = client.post("/ivr/input", json={"session_id": sid, "value": bad})
            assert r.status_code < 500, f"Got {r.status_code} for input '{bad}'"
        sessions.pop(sid, None)

    def test_reuse_session_after_hangup_is_safe(self):
        """Once a session is deleted on hangup, a late duplicate request must not 500."""
        sid, _ = dial("9200000064")
        press(sid, "3"); press(sid, "12627")   # cancel → hangup → session deleted
        assert sid not in sessions

        r = client.post("/ivr/input", json={"session_id": sid, "value": "1"})
        assert r.status_code == 200
        assert r.json()["action"] == "hangup"

    def test_booking_invalid_train_then_valid(self):
        """After an invalid train choice, correct input must still succeed."""
        sid, _ = dial("9200000065")
        press(sid, "1"); press(sid, "1"); press(sid, "2"); press(sid, "1")
        bad = press(sid, "9")
        assert "Invalid" in bad["prompt"]
        d = press(sid, "1")   # Valid on retry
        assert "booked successfully" in d["prompt"].lower()

    def test_word_input_book_ticket_triggers_booking(self):
        """
        The web simulator and voice_ivr both send mapped text — e.g. 'book'.
        detect_intent must handle words, not just digits.
        """
        sid, _ = dial("9200000066")
        d = press(sid, "book")
        assert "Source Station" in d["prompt"]
        sessions.pop(sid, None)

    def test_word_input_pnr_triggers_pnr_flow(self):
        sid, _ = dial("9200000067")
        d = press(sid, "pnr")
        assert "PNR" in d["prompt"]
        sessions.pop(sid, None)
    