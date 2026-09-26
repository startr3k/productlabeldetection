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


def test_scan_renders_extracted_html_unescaped(
    client, auth, app_module, monkeypatch, storage_blobs
):
    """Records that OCR output reaches the page as live markup (issue #9).

    parse_table builds the table by string concatenation with no escaping and
    main.py wraps it in Markup(), so a tag in extracted text is rendered rather
    than shown. Invert this assertion when issue #9 is fixed.
    """
    storage_blobs([Blob("a.gif")])
    app_module.productlist = ["a.gif"]
    monkeypatch.setattr(
        app_module,
        "parse_table",
        lambda filename: ["<td><script>x</script></td>", "origin"],
    )

    body = client.post(
        "/package", headers=AUTH_HEADER, data={"img": "/a.gif", "user": "alice"}
    ).get_data(as_text=True)

    assert "<script>x</script>" in body
    assert "&lt;script&gt;" not in body


def test_scan_renders_client_supplied_user(
    client, auth, app_module, monkeypatch, storage_blobs
):
    """Records that the POST trusts the request body for identity (issue #8).

    The handler renders request.form["user"] rather than the verified token, so
    the displayed name is whatever the caller sent.
    """
    storage_blobs([Blob("a.gif")])
    app_module.productlist = ["a.gif"]
    monkeypatch.setattr(app_module, "parse_table", lambda filename: ["<p>ok</p>", ""])

    body = client.post(
        "/package",
        headers=AUTH_HEADER,
        data={"img": "/a.gif", "user": "not-the-token-owner"},
    ).get_data(as_text=True)

    assert "not-the-token-owner" in body


def test_verify_known_user_returns_one(client, datastore_results):
    datastore_results([object()])

    response = client.post("/verify", data={"email": "alice@example.com"})

    assert response.get_data(as_text=True) == "1"


def test_verify_unknown_user_returns_zero(client, datastore_results):
    datastore_results([])

    response = client.post("/verify", data={"email": "nobody@example.com"})

    assert response.get_data(as_text=True) == "0"


def test_scan_without_image_returns_400(client, auth, app_module):
    response = client.post("/package", headers=AUTH_HEADER, data={"user": "alice"})

    assert response.status_code == 400


def test_verify_without_email_returns_400(client):
    assert client.post("/verify", data={}).status_code == 400


@pytest.mark.xfail(
    reason="issue #7: /verify carries no @jwt_authenticated decorator, so it "
    "answers unauthenticated callers and reveals whether an email is registered"
)
def test_verify_requires_authentication(client, datastore_results):
    datastore_results([object()])

    response = client.post("/verify", data={"email": "alice@example.com"})

    assert response.status_code == 401


@pytest.mark.xfail(
    reason="issue #12: productlist is a module global populated only by "
    "GET /package, so on a fresh worker POST /package renders no products"
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
