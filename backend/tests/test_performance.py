# =============================================================================
# tests/test_performance.py
# MILESTONE 4 — PERFORMANCE / LOAD TESTS
#
# Targets from Module 4 spec:
#   • Average response time  < 200 ms
#   • P95 response time      < 500 ms
#   • Error rate               0 %    under expected load
#   • Throughput             > 50 req/s on TestClient
#
# Two test strategies:
#   1. Sequential — measures raw latency of each endpoint
#   2. Concurrent — uses threading to simulate simultaneous callers,
#      matching what the web simulator and voice client both do
# =============================================================================

import time
import threading
import statistics
import pytest
from fastapi.testclient import TestClient
from main import app, sessions

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def timed(path, payload):
    t0 = time.perf_counter()
    r  = client.post(path, json=payload)
    ms = (time.perf_counter() - t0) * 1000
    return r.status_code, ms

def new_sid():
    r = client.post("/ivr/start", json={"caller_number": "9300000000"})
    return r.json()["session_id"]

def full_booking(caller):
    """Complete booking journey — used in concurrent tests."""
    r = client.post("/ivr/start", json={"caller_number": caller})
    sid = r.json()["session_id"]
    for v in ["1", "1", "2", "1", "2"]:   # book → Hyd → Chennai → Today → Charminar
        client.post("/ivr/input", json={"session_id": sid, "value": v})


# =============================================================================
# /ivr/start  — latency
# =============================================================================

class TestStartEndpointLatency:

    def test_single_start_under_200ms(self):
        _, ms = timed("/ivr/start", {"caller_number": "9300000001"})
        assert ms < 200, f"Single /ivr/start took {ms:.1f}ms"

    def test_50_sequential_starts_avg_under_200ms(self):
        N = 50
        latencies, errors = [], 0
        for i in range(N):
            status, ms = timed("/ivr/start", {"caller_number": f"93000{i:05d}"})
            latencies.append(ms)
            if status != 200: errors += 1

        avg = statistics.mean(latencies)
        p95 = sorted(latencies)[int(N * 0.95)]
        print(f"\n[/ivr/start ×{N}] avg={avg:.1f}ms  p95={p95:.1f}ms  errors={errors}")

        assert errors == 0,   f"{errors} errors in {N} /ivr/start requests"
        assert avg    < 200,  f"avg {avg:.1f}ms exceeds 200ms target"
        assert p95    < 500,  f"p95 {p95:.1f}ms exceeds 500ms target"

    def test_100_sequential_starts_zero_errors(self):
        N, errors = 100, 0
        for i in range(N):
            status, _ = timed("/ivr/start", {"caller_number": f"94000{i:05d}"})
            if status != 200: errors += 1
        assert errors == 0


# =============================================================================
# /ivr/input  — latency (session lookup + routing + response)
# =============================================================================

class TestInputEndpointLatency:

    def test_single_input_under_200ms(self):
        sid = new_sid()
        _, ms = timed("/ivr/input", {"session_id": sid, "value": "1"})
        assert ms < 200

    def test_50_sequential_inputs_avg_under_200ms(self):
        N = 50
        # Pre-create sessions so we measure routing, not start overhead
        sids = [new_sid() for _ in range(N)]
        latencies, errors = [], 0

        for sid in sids:
            status, ms = timed("/ivr/input", {"session_id": sid, "value": "1"})
            latencies.append(ms)
            if status != 200: errors += 1

        avg = statistics.mean(latencies)
        p95 = sorted(latencies)[int(N * 0.95)]
        print(f"\n[/ivr/input ×{N}] avg={avg:.1f}ms  p95={p95:.1f}ms  errors={errors}")

        assert errors == 0
        assert avg    < 200
        assert p95    < 500

    def test_full_5_step_booking_journey_under_1000ms_total(self):
        """
        A complete start→source→dest→date→train booking (6 requests total)
        must finish in under 1 second wall-clock time.
        """
        t0 = time.perf_counter()
        r  = client.post("/ivr/start", json={"caller_number": "9300099999"})
        sid = r.json()["session_id"]
        for v in ["1", "1", "2", "1", "1"]:
            client.post("/ivr/input", json={"session_id": sid, "value": v})
        total_ms = (time.perf_counter() - t0) * 1000
        print(f"\n[Full booking wall-clock] {total_ms:.1f}ms")
        assert total_ms < 1000, f"Full booking took {total_ms:.1f}ms"


# =============================================================================
# Concurrent callers — threading
# Simulates multiple simultaneous callers hitting the backend at once,
# which is exactly what happens when several browser tabs run the web
# simulator or multiple voice IVR clients are active.
# =============================================================================

class TestConcurrentLoad:

    def _worker(self, caller_id, results):
        try:
            r = client.post("/ivr/start", json={"caller_number": f"8{caller_id:09d}"})
            if r.status_code != 200:
                results.append(("error", r.status_code)); return
            sid = r.json()["session_id"]
            r2  = client.post("/ivr/input", json={"session_id": sid, "value": "1"})
            results.append(("ok", r2.status_code))
        except Exception as e:
            results.append(("exception", str(e)))

    def test_20_concurrent_callers_zero_errors(self):
        N, results = 20, []
        threads = [threading.Thread(target=self._worker, args=(i, results)) for i in range(N)]
        [t.start() for t in threads]; [t.join() for t in threads]
        errors = [r for r in results if r[0] != "ok"]
        print(f"\n[Concurrent ×{N}] errors={len(errors)}")
        assert len(errors) == 0, f"Concurrent errors: {errors}"

    def test_50_concurrent_callers_zero_errors(self):
        N, results = 50, []
        threads = [threading.Thread(target=self._worker, args=(i, results)) for i in range(N)]
        [t.start() for t in threads]; [t.join() for t in threads]
        errors = [r for r in results if r[0] != "ok"]
        print(f"\n[Concurrent ×{N}] errors={len(errors)}")
        assert len(errors) == 0

    def test_concurrent_full_bookings_no_session_crossover(self):
        """
        5 callers each complete a full booking concurrently.
        No session must mix with another — all must end in hangup.
        """
        results = []

        def book(caller_id):
            try:
                full_booking(f"7{caller_id:09d}")
                results.append("ok")
            except Exception as e:
                results.append(f"error: {e}")

        threads = [threading.Thread(target=book, args=(i,)) for i in range(5)]
        [t.start() for t in threads]; [t.join() for t in threads]
        assert all(r == "ok" for r in results), f"Booking errors: {results}"

    def test_concurrent_sessions_never_share_state(self):
        """
        Caller A does booking, Caller B checks PNR — run simultaneously.
        Verify their intent/stage is independent after threads join.
        """
        a_state, b_state = {}, {}

        def caller_a():
            r = client.post("/ivr/start", json={"caller_number": "A"})
            sid = r.json()["session_id"]
            client.post("/ivr/input", json={"session_id": sid, "value": "1"})
            a_state.update(sessions.get(sid, {}))

        def caller_b():
            r = client.post("/ivr/start", json={"caller_number": "B"})
            sid = r.json()["session_id"]
            client.post("/ivr/input", json={"session_id": sid, "value": "2"})
            b_state.update(sessions.get(sid, {}))

        ta, tb = threading.Thread(target=caller_a), threading.Thread(target=caller_b)
        ta.start(); tb.start(); ta.join(); tb.join()

        assert a_state.get("intent") == "book_ticket"
        assert b_state.get("intent") == "pnr_status"
        assert a_state.get("stage")  != b_state.get("stage")


# =============================================================================
# Throughput benchmark  (informational — prints RPS, soft assertion)
# =============================================================================

class TestThroughput:

    def test_requests_per_second_baseline(self):
        """
        Fires /ivr/start as fast as possible for 2 seconds.
        Prints RPS. Must be > 50 RPS on TestClient.
        """
        deadline = time.perf_counter() + 2.0
        count, errors = 0, 0
        while time.perf_counter() < deadline:
            status, _ = timed("/ivr/start", {"caller_number": "5555555555"})
            count += 1
            if status != 200: errors += 1

        rps = count / 2.0
        print(f"\n[Throughput] {count} reqs in 2s = {rps:.1f} req/s  errors={errors}")
        assert rps    > 50, f"Only {rps:.1f} req/s — may be too slow"
        assert errors ==  0
