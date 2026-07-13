"""End-to-end route test for POST /sources/paste-link, via FastAPI's TestClient.
trafilatura is monkeypatched so no real network fetch happens."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routes.sources as sources_module
import app.sources.paste_link as paste_link_module
from app.engine.memory import MemoryStore
from app.main import app


def _patch_memory_store(monkeypatch, tmp_path):
    monkeypatch.setattr(sources_module, "MemoryStore", lambda: MemoryStore(path=tmp_path / "memory.json"))


def test_paste_link_route_returns_attributed_brief(tmp_path, monkeypatch):
    _patch_memory_store(monkeypatch, tmp_path)
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: "<html>fake</html>")
    monkeypatch.setattr(paste_link_module.trafilatura, "extract", lambda html: "Extracted article body.")
    monkeypatch.setattr(
        paste_link_module.trafilatura,
        "extract_metadata",
        lambda html, default_url=None: SimpleNamespace(title="Test Article", author="A. Writer"),
    )

    client = TestClient(app)
    response = client.post("/sources/paste-link", json={"url": "https://example.com/article"})

    assert response.status_code == 200
    body = response.json()
    assert body["brief"]["requires_citation"] is True
    assert len(body["brief"]["sources"]) == 1
    assert body["brief"]["sources"][0]["url"] == "https://example.com/article"
    assert body["brief"]["topic_name"] == "Test Article"


def test_paste_link_route_returns_422_on_fetch_failure(tmp_path, monkeypatch):
    _patch_memory_store(monkeypatch, tmp_path)
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: None)

    client = TestClient(app)
    response = client.post("/sources/paste-link", json={"url": "https://example.com/dead-link"})

    assert response.status_code == 422
