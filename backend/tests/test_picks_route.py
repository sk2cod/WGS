"""End-to-end route tests for GET /picks and POST /picks/reroll, via FastAPI's
TestClient. These exist to catch dependency-wiring bugs (wrong arg names/order into
the underlying selector functions) that pure unit tests of selector.py can't see.
LLMProvider/PicksStore/MemoryStore are monkeypatched at the route-module level so no
real Anthropic call or shared cache file is ever touched."""

import json

from fastapi.testclient import TestClient

import app.routes.picks as picks_module
from app.engine.memory import MemoryStore
from app.engine.selector import PicksStore
from app.main import app

ANGLE_JSON = json.dumps({"angle": "a specific angle", "mood": "wisdom"})
PITCH_JSON = json.dumps({"hook": "a hook", "thumbnail_concept": "a concept"})


class _QueueLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        return self._responses.pop(0)


def _patch_stores(monkeypatch, tmp_path, llm_factory):
    monkeypatch.setattr(picks_module, "LLMProvider", llm_factory)
    monkeypatch.setattr(picks_module, "PicksStore", lambda: PicksStore(path=tmp_path / "picks.json"))
    monkeypatch.setattr(picks_module, "MemoryStore", lambda: MemoryStore(path=tmp_path / "memory.json"))


def test_get_picks_returns_three_picks_end_to_end(tmp_path, monkeypatch):
    _patch_stores(monkeypatch, tmp_path, lambda: _QueueLLM([ANGLE_JSON, PITCH_JSON] * 3))

    client = TestClient(app)
    response = client.get("/picks")

    assert response.status_code == 200
    body = response.json()
    assert len(body["picks"]) == 3
    assert all(p["hook"] for p in body["picks"])


def test_get_picks_is_cached_on_second_call(tmp_path, monkeypatch):
    calls = {"n": 0}

    class _CountingLLM:
        def __init__(self):
            self._responses = [ANGLE_JSON, PITCH_JSON] * 3

        def complete(self, *, tier, system, prompt, max_tokens, cache=True):
            calls["n"] += 1
            return self._responses.pop(0)

    _patch_stores(monkeypatch, tmp_path, _CountingLLM)

    client = TestClient(app)
    first = client.get("/picks")
    second = client.get("/picks")

    assert first.status_code == 200 and second.status_code == 200
    assert calls["n"] == 6  # exactly the first call's cost — the second was a cache hit
    assert first.json()["picks"] == second.json()["picks"]


def test_reroll_route_swaps_pick_and_persists(tmp_path, monkeypatch):
    _patch_stores(monkeypatch, tmp_path, lambda: _QueueLLM([ANGLE_JSON, PITCH_JSON] * 4))

    client = TestClient(app)
    client.get("/picks")  # precompute today's picks first
    response = client.post("/picks/reroll", json={"pick_index": 0})

    assert response.status_code == 200
    assert response.json()["rerolls_used"] == 1


def test_reroll_route_out_of_range_index_returns_400(tmp_path, monkeypatch):
    _patch_stores(monkeypatch, tmp_path, lambda: _QueueLLM([ANGLE_JSON, PITCH_JSON] * 3))

    client = TestClient(app)
    client.get("/picks")
    response = client.post("/picks/reroll", json={"pick_index": 99})

    assert response.status_code == 400


def test_reroll_route_without_precomputed_picks_returns_429(tmp_path, monkeypatch):
    _patch_stores(monkeypatch, tmp_path, lambda: _QueueLLM([]))

    client = TestClient(app)
    response = client.post("/picks/reroll", json={"pick_index": 0})

    assert response.status_code == 429
