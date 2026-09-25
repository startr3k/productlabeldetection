"""Shared pytest fixtures and dependency stubs.

The repository imports Google Cloud / Firebase clients and an unused scientific
stack at module import time, and ``middleware`` calls
``firebase_admin.initialize_app()`` on import. None of that is needed to exercise
the repository logic, and none of it can run without credentials, so this module
installs lightweight stub modules into ``sys.modules`` *before* the repo modules
are imported. pytest imports this file before any test module, so the stubs are
always in place first.
"""

from __future__ import annotations

import sys
import types
from unittest import mock

import flask
import markupsafe
import pytest

# main.py does ``from flask import ... Markup ...``, which Flask 2.3+ removed.
# Shim it so the app module imports under a modern Flask.
if not hasattr(flask, "Markup"):
    flask.Markup = markupsafe.Markup


def _mod(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _simple_type(name: str) -> type:
    # Accept any constructor arguments: callers build some of these with
    # positional config (e.g. structlog.processors.TimeStamper("iso")).
    return type(name, (), {"__init__": lambda self, *args, **kwargs: None})


def _install_stubs() -> None:
    # --- google.cloud -----------------------------------------------------
    google = _mod("google")
    cloud = _mod("google.cloud")
    google.cloud = cloud

    storage = _mod("google.cloud.storage")
    cloud.storage = storage

    class _StorageClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_blobs(self, bucket):
            return []

        def bucket(self, name):
            raise NotImplementedError

    storage.Client = _StorageClient
    storage.Blob = _simple_type("Blob")
    storage.Blob_exists = None

    datastore = _mod("google.cloud.datastore")
    cloud.datastore = datastore
    datastore.Client = _simple_type("Client")
    datastore.Entity = _simple_type("Entity")

    for version in ("documentai_v1beta2", "documentai_v1beta3"):
        docai = _mod(f"google.cloud.{version}")
        setattr(cloud, version, docai)
        docai_types = _mod(f"google.cloud.{version}.types")
        docai.types = docai_types
        for type_name in (
            "GcsSource",
            "InputConfig",
            "TableExtractionParams",
            "ProcessDocumentRequest",
            "Document",
        ):
            setattr(
                docai_types,
                type_name,
                lambda **kwargs: types.SimpleNamespace(**kwargs),
            )
        docai.DocumentUnderstandingServiceClient = _simple_type(
            "DocumentUnderstandingServiceClient"
        )

    language = _mod("google.cloud.language_v1")
    cloud.language_v1 = language
    language.LanguageServiceClient = _simple_type("LanguageServiceClient")
    language.Document = _simple_type("Document")
    language.EncodingType = _simple_type("EncodingType")
    language.Entity = _simple_type("Entity")

    # --- firebase_admin ---------------------------------------------------
    firebase_admin = _mod("firebase_admin")
    firebase_auth = _mod("firebase_admin.auth")
    firebase_admin.auth = firebase_auth
    firebase_admin.initialize_app = lambda *args, **kwargs: None
    firebase_auth.verify_id_token = lambda token, **kwargs: {"uid": "stub-uid"}
    firebase_auth.get_user = lambda uid, **kwargs: types.SimpleNamespace(
        display_name=None, email=None
    )

    # --- structlog --------------------------------------------------------
    # middleware uses structlog private namespaces in type annotations, which
    # are evaluated at function-definition time, so they must exist.
    structlog = _mod("structlog")
    structlog.configure = lambda **kwargs: None
    structlog.get_logger = lambda *args, **kwargs: mock.MagicMock()

    structlog_stdlib = _mod("structlog.stdlib")
    structlog.stdlib = structlog_stdlib
    structlog_stdlib.add_log_level = lambda *args, **kwargs: None
    structlog_stdlib.PositionalArgumentsFormatter = _simple_type(
        "PositionalArgumentsFormatter"
    )
    structlog_stdlib.BoundLogger = _simple_type("BoundLogger")

    structlog_processors = _mod("structlog.processors")
    structlog.processors = structlog_processors
    structlog_processors.TimeStamper = _simple_type("TimeStamper")
    structlog_processors.JSONRenderer = _simple_type("JSONRenderer")

    structlog_loggers = _mod("structlog._loggers")
    structlog._loggers = structlog_loggers
    structlog_loggers.PrintLogger = _simple_type("PrintLogger")

    structlog_config = _mod("structlog._config")
    structlog._config = structlog_config
    structlog_config.BoundLoggerLazyProxy = _simple_type("BoundLoggerLazyProxy")

    # --- imported but unused at runtime -----------------------------------
    matplotlib = _mod("matplotlib")
    matplotlib_pyplot = _mod("matplotlib.pyplot")
    matplotlib.pyplot = matplotlib_pyplot

    wand = _mod("wand")
    wand_image = _mod("wand.image")
    wand.image = wand_image
    wand_image.Image = _simple_type("Image")

    skimage = _mod("skimage")
    for submodule_name in ("data", "io", "filters"):
        submodule = _mod(f"skimage.{submodule_name}")
        setattr(skimage, submodule_name, submodule)
    skimage.filters.threshold_otsu = lambda *args, **kwargs: None

    pil = _mod("PIL")
    for submodule_name in ("Image", "ImageDraw", "ImageEnhance"):
        setattr(pil, submodule_name, _simple_type(submodule_name))

    _mod("numpy")
    _mod("pandas")


_install_stubs()


@pytest.fixture(autouse=True)
def _reset_middleware_display_name():
    """middleware keeps a process-global displayName; isolate tests from it."""
    middleware = sys.modules.get("middleware")
    if middleware is not None:
        middleware.displayName = ""
    yield
    middleware = sys.modules.get("middleware")
    if middleware is not None:
        middleware.displayName = ""


@pytest.fixture
def app_module():
    """Import the Flask app and reset its module-level state."""
    import main

    main.productlist = []
    main.BUCKET_LABEL = "test-bucket"
    return main


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


@pytest.fixture
def auth(monkeypatch):
    """Drive the stubbed Firebase auth with a chosen user."""
    import middleware

    def set_user(uid="uid-alice", email="alice@example.com", name=None):
        def _verify(token, **kwargs):
            if token == "invalid":
                raise ValueError("invalid token")
            return {"uid": uid}

        monkeypatch.setattr(middleware.auth, "verify_id_token", _verify)
        monkeypatch.setattr(
            middleware.auth,
            "get_user",
            lambda user_id, **kwargs: types.SimpleNamespace(
                display_name=name, email=email
            ),
        )

    set_user()
    return set_user


@pytest.fixture
def storage_blobs(monkeypatch, app_module):
    """Replace google.cloud.storage.Client with a fixed blob list."""

    def _set(blobs):
        class _Client:
            def list_blobs(self, bucket):
                return list(blobs)

        monkeypatch.setattr(app_module.storage, "Client", lambda *a, **k: _Client())

    return _set


@pytest.fixture
def datastore_results(monkeypatch, app_module):
    """Replace google.cloud.datastore.Client with a fixed query result set."""

    def _set(entities):
        class _Query:
            def add_filter(self, *args, **kwargs):
                return self

            def fetch(self):
                return iter(entities)

        monkeypatch.setattr(
            app_module.datastore,
            "Client",
            lambda *a, **k: types.SimpleNamespace(query=lambda kind=None, **kw: _Query()),
        )

    return _set
