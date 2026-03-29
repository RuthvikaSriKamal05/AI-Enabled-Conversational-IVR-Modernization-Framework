# =============================================================================
# tests/conftest.py
# Shared fixtures for the IRCTC IVR Milestone 4 test suite.
# Automatically loaded by pytest before any test module runs.
# =============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from fastapi.testclient import TestClient
from main import app, sessions


# ---------------------------------------------------------------------------
# CLIENT FIXTURE
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    """Single TestClient shared across the whole test session."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# SESSION CLEANUP — runs before AND after every single test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_sessions():
    """
    Wipes the in-memory sessions dict before each test so no state leaks
    between tests. autouse=True means every test gets this automatically.
    """
    sessions.clear()
    yield
    sessions.clear()


# ---------------------------------------------------------------------------
# CONVENIENCE FIXTURES  (map to actual main.py stages)
# ---------------------------------------------------------------------------

@pytest.fixture
def started_session(client):
    """Returns (session_id, prompt) for a freshly dialled call."""
    resp = client.post("/ivr/start", json={"caller_number": "9000000000"})
    d = resp.json()
    return d["session_id"], d["prompt"]


@pytest.fixture
def booking_at_source(client, started_session):
    """
    Caller pressed '1' on main menu.
    Session is now at stage='source', intent='book_ticket'.
    """
    sid, _ = started_session
    client.post("/ivr/input", json={"session_id": sid, "value": "1"})
    return sid


@pytest.fixture
def pnr_session(client, started_session):
    """Session is at stage='pnr_number', intent='pnr_status'."""
    sid, _ = started_session
    client.post("/ivr/input", json={"session_id": sid, "value": "2"})
    return sid


@pytest.fixture
def care_session(client, started_session):
    """Session is at stage='customer_care', intent='agent'."""
    sid, _ = started_session
    client.post("/ivr/input", json={"session_id": sid, "value": "9"})
    return sid
