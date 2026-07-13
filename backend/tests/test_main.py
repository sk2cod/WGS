from app.main import app


def test_generate_route_is_registered():
    schema = app.openapi()
    assert "/generate" in schema["paths"]
    assert "post" in schema["paths"]["/generate"]


def test_picks_routes_are_registered():
    schema = app.openapi()
    assert "get" in schema["paths"]["/picks"]
    assert "post" in schema["paths"]["/picks/reroll"]


def test_paste_link_route_is_registered():
    schema = app.openapi()
    assert "post" in schema["paths"]["/sources/paste-link"]


def test_topics_route_returns_full_catalog():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/topics")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 18
    assert {"id", "name", "categories", "primary_category"} <= body[0].keys()
