"""Tests for middleware.jwt_authenticated and the shared display name."""

import threading

import pytest
from flask import Flask, request

import middleware
from helpers import AUTH_HEADER, Blob


@pytest.fixture
def protected_client(auth):
    app = Flask(__name__)

    @app.route("/protected")
    @middleware.jwt_authenticated
    def protected_route():
        return "uid=" + str(getattr(request, "uid", None))

    return app.test_client()


def test_missing_authorization_header_is_unauthorized(protected_client):
    assert protected_client.get("/protected").status_code == 401


def test_invalid_token_is_forbidden(protected_client):
    response = protected_client.get(
        "/protected", headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 403
    # The raw exception text is echoed back to the caller (issue 16).
    assert "Error with authentication" in response.get_data(as_text=True)


def test_valid_token_runs_handler_and_sets_uid(protected_client):
    response = protected_client.get("/protected", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert "uid=uid-alice" in response.get_data(as_text=True)


@pytest.mark.xfail(
    reason="jwt_authenticated does header.split(' ')[1] without bounds checking, "
    "so a malformed Authorization header raises IndexError (issue 15)"
)
def test_malformed_authorization_header_returns_400(protected_client):
    response = protected_client.get("/protected", headers={"Authorization": "Bearer"})

    assert response.status_code == 400


@pytest.mark.xfail(
    reason="middleware.displayName is a module global, so a concurrent request "
    "can overwrite the name rendered for another user (issue 2)"
)
def test_display_name_is_not_shared_across_concurrent_requests(
    app_module, auth, storage_blobs, monkeypatch
):
    alice_verified = threading.Event()
    bob_finished = threading.Event()
    state = {"delayed": False}
    real_get_display_name = middleware.getDisplayName

    def delayed_get_display_name():
        # Hold alice's request after her token was verified but before the page
        # renders, so bob's request can overwrite the shared displayName.
        if not state["delayed"]:
            state["delayed"] = True
            alice_verified.set()
            bob_finished.wait(5)
        return real_get_display_name()

    monkeypatch.setattr(app_module, "getDisplayName", delayed_get_display_name)
    storage_blobs([Blob("a.gif")])

    results = {}

    def alice_request():
        results["alice"] = (
            app_module.app.test_client()
            .get("/package", headers=AUTH_HEADER)
            .get_data(as_text=True)
        )

    def bob_request():
        assert alice_verified.wait(5)
        auth(uid="uid-bob", email="bob@example.com")
        results["bob"] = (
            app_module.app.test_client()
            .get("/package", headers=AUTH_HEADER)
            .get_data(as_text=True)
        )
        bob_finished.set()

    auth(uid="uid-alice", email="alice@example.com")
    threads = [
        threading.Thread(target=alice_request),
        threading.Thread(target=bob_request),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert "bob@example.com" in results["bob"]
    assert "alice@example.com" in results["alice"]
