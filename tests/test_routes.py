"""Tests for the Flask routes in main.py."""

import pytest

from helpers import AUTH_HEADER, Blob


def test_index_renders_login_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "signInButton" in response.get_data(as_text=True)


def test_package_requires_authentication(client):
    assert client.get("/package").status_code == 401


def test_package_lists_only_gif_blobs(client, auth, storage_blobs):
    storage_blobs([Blob("a.gif"), Blob("b.png", "image/png"), Blob("c.gif")])

    response = client.get("/package", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "a.gif" in body
    assert "c.gif" in body
    assert "b.png" not in body


def test_package_selects_first_product(client, auth, storage_blobs):
    storage_blobs([Blob("z.gif"), Blob("a.gif")])

    body = client.get("/package", headers=AUTH_HEADER).get_data(as_text=True)

    assert 'value="/z.gif"' in body


def test_scan_runs_parse_table_with_bare_filename(
    client, auth, app_module, monkeypatch, storage_blobs
):
    storage_blobs([Blob("a.gif")])
    app_module.productlist = ["a.gif"]
    seen = {}

    def fake_parse_table(filename):
        seen["filename"] = filename
        return ["<thead><tr><th>N</th></tr></thead>", "Made in Australia"]

    monkeypatch.setattr(app_module, "parse_table", fake_parse_table)

    response = client.post(
        "/package", headers=AUTH_HEADER, data={"img": "/a.gif", "user": "alice"}
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "<thead><tr><th>N</th></tr></thead>" in body
    assert "Made in Australia" in body
    # The leading slash from the form value is stripped before the GCS lookup.
    assert seen["filename"] == "a.gif"


def test_scan_uses_token_identity_not_client_input(
    client, auth, app_module, monkeypatch, storage_blobs
):
    storage_blobs([Blob("a.gif")])
    monkeypatch.setattr(app_module, "parse_table", lambda filename: ["", ""])

    body = client.post(
        "/package",
        headers=AUTH_HEADER,
        data={"img": "/a.gif", "user": "<script>alert(1)</script>"},
    ).get_data(as_text=True)

    assert "<script>alert(1)</script>" not in body
    assert "alice@example.com" in body


def test_verify_known_user_returns_one(client, auth, datastore_results):
    datastore_results([object()])

    response = client.post("/verify", headers=AUTH_HEADER)

    assert response.get_data(as_text=True) == "1"


def test_verify_unknown_user_returns_zero(client, auth, datastore_results):
    datastore_results([])

    response = client.post("/verify", headers=AUTH_HEADER)

    assert response.get_data(as_text=True) == "0"


def test_scan_without_image_returns_400(client, auth, app_module):
    response = client.post("/package", headers=AUTH_HEADER, data={"user": "alice"})

    assert response.status_code == 400


def test_verify_requires_authentication(client, datastore_results):
    datastore_results([object()])

    assert client.post("/verify").status_code == 401


def test_verify_queries_the_token_email_not_client_input(client, auth, datastore_results):
    captured = datastore_results([object()])

    # A caller cannot probe whether an arbitrary address is registered.
    response = client.post(
        "/verify", headers=AUTH_HEADER, data={"email": "attacker@example.com"}
    )

    assert response.get_data(as_text=True) == "1"
    assert captured["filters"] == [("Email", "=", "alice@example.com")]


@pytest.mark.xfail(
    reason="productlist is a module global populated by GET /package, so on a "
    "fresh worker POST /package renders an empty firstProduct (issue 13)"
)
def test_scan_on_fresh_worker_keeps_first_product(
    client, auth, app_module, monkeypatch
):
    app_module.productlist = []
    monkeypatch.setattr(
        app_module, "parse_table", lambda filename: ["<p>ok</p>", "x"]
    )

    body = client.post(
        "/package", headers=AUTH_HEADER, data={"img": "/a.gif", "user": "alice"}
    ).get_data(as_text=True)

    assert 'value="/a.gif"' in body
