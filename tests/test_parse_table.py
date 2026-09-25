"""Tests for DocAI.parse_table against a fake Document AI response."""

import types

import pytest

import DocAI
from helpers import build_document

NUTRITION_HEADER = [["Nutrition", "Information"]]
NUTRITION_BODY = [
    ["Energy", "1200"],
    ["Protein", "5.2"],
    ["Fat", "3"],
    ["Carbohydrate", "2o"],
]


@pytest.fixture
def fake_document(monkeypatch):
    """Patch the Document AI client and the Datastore lookup."""

    def _install(document):
        monkeypatch.setattr(
            DocAI.documentai_v1beta2,
            "DocumentUnderstandingServiceClient",
            lambda *a, **k: types.SimpleNamespace(
                process_document=lambda request: document
            ),
        )
        monkeypatch.setattr(DocAI, "query_datastore", lambda filename: "MADE IN AUSTRALIA")

    return _install


def test_nutrition_table_is_extracted(fake_document):
    fake_document(build_document(NUTRITION_HEADER, NUTRITION_BODY))

    result = DocAI.parse_table("sample.gif")

    assert isinstance(result, list)
    assert len(result) == 2

    html = result[0]
    assert "Nutrition Information" in html
    assert "<td>Energy</td>" in html
    assert "<td>120g</td>" in html
    assert "<td>5.2</td>" in html
    assert "<td>20</td>" in html
    # The repeated in-table header row is discarded in favour of the generated one.
    assert "<td>Nutrition</td>" not in html
    # The filename is embedded so package.js can tell which product is linked.
    assert "file='sample.gif'" in html


def test_made_in_australia_text_comes_from_datastore(fake_document):
    fake_document(build_document(NUTRITION_HEADER, NUTRITION_BODY))

    result = DocAI.parse_table("sample.gif")

    assert result[1] == "MADE IN AUSTRALIA"


def test_non_nutrition_table_is_ignored(fake_document):
    fake_document(
        build_document([["Label", "Value"]], [["Energy", "1"], ["Protein", "2"]])
    )

    result = DocAI.parse_table("sample.gif")

    assert result[0] == ""


@pytest.mark.xfail(
    reason="parse_table emits output only inside the header_rows loop, so a table "
    "with no header rows is dropped entirely (issue 17)"
)
def test_headerless_nutrition_table_is_dropped(fake_document):
    fake_document(build_document([], NUTRITION_BODY))

    result = DocAI.parse_table("sample.gif")

    assert "Nutrition Information" in result[0]


def _patch_datastore(monkeypatch, entities):
    class _Query:
        def key_filter(self, key, operator):
            return self

        def fetch(self):
            return iter(entities)

    fake_client = types.SimpleNamespace(
        query=lambda kind=None, **kwargs: _Query(),
        key=lambda kind=None, name=None: ("key", kind, name),
    )
    monkeypatch.setattr(DocAI.datastore, "Client", lambda *a, **k: fake_client)


def test_query_datastore_returns_stored_text(monkeypatch):
    _patch_datastore(monkeypatch, [{"Text": "Made in Australia"}])

    assert DocAI.query_datastore("sample.gif") == "Made in Australia"


def test_query_datastore_returns_empty_when_entity_missing(monkeypatch):
    _patch_datastore(monkeypatch, [])

    assert DocAI.query_datastore("sample.gif") == ""


def test_cell_text_is_html_escaped(fake_document):
    fake_document(
        build_document(
            NUTRITION_HEADER,
            [
                ["Energy", "<script>alert(1)</script>"],
                ["Protein", "5.2"],
                ["Fat", "3"],
                ["Carbohydrate", "2"],
            ],
        )
    )

    html = DocAI.parse_table("sample.gif")[0]

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_filename_is_html_escaped(fake_document):
    fake_document(build_document(NUTRITION_HEADER, NUTRITION_BODY))

    html = DocAI.parse_table("bad'><script>alert(1)</script>.gif")[0]

    assert "<script>" not in html
