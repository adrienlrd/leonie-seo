"""Tests for app.embeddings.encoder — E5 task prefixes and thread safety.

Covers the lot 4 wave 2 fix that splits encode_texts into explicit
query/passage modes so callers can't silently tag passages as queries.
The real sentence-transformers model is too heavy to load in tests, so
SentenceTransformer is monkey-patched with a deterministic stub.
"""

from __future__ import annotations

import pytest

from app.embeddings import encoder as encoder_module


class _StubST:
    """Records the prefixed inputs and returns a deterministic vector per text."""

    def __init__(self, _model_name: str) -> None:
        self.last_inputs: list[str] = []

    def encode(self, texts: list[str], *, normalize_embeddings: bool = True):  # noqa: ARG002
        # Record inputs so tests can assert the right prefix was applied.
        self.last_inputs = list(texts)
        # Return one fake 4-d vector per input — content depends on prefix
        # so query/passage embeddings differ (mimics real E5 behaviour).
        out = []
        for t in texts:
            if t.startswith("query: "):
                out.append([1.0, 0.0, 0.0, 0.0])
            elif t.startswith("passage: "):
                out.append([0.0, 1.0, 0.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0, 0.0])

        # Mimic numpy .tolist() — already a list of lists, so just return self
        class _Arr(list):
            def tolist(self):
                return list(self)

        return _Arr(out)


@pytest.fixture()
def stub(monkeypatch):
    """Replace SentenceTransformer with a stub and reset the cache."""
    monkeypatch.setattr(encoder_module, "_encoder", None)
    stub_inst = {"value": None}

    def _make(model_name):
        stub_inst["value"] = _StubST(model_name)
        return stub_inst["value"]

    # The encoder lazily imports SentenceTransformer; intercept the import path.
    import sys
    import types

    fake_module = types.SimpleNamespace(SentenceTransformer=_make)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    yield stub_inst
    monkeypatch.setattr(encoder_module, "_encoder", None)


def test_encode_query_applies_query_prefix(stub):
    vec = encoder_module.encode_query("harnais chien")
    assert stub["value"].last_inputs == ["query: harnais chien"]
    assert vec == [1.0, 0.0, 0.0, 0.0]


def test_encode_passage_applies_passage_prefix(stub):
    vec = encoder_module.encode_passage("Harnais haute couture pour chien")
    assert stub["value"].last_inputs == ["passage: Harnais haute couture pour chien"]
    assert vec == [0.0, 1.0, 0.0, 0.0]


def test_encode_texts_mode_query_applies_query_prefix(stub):
    vecs = encoder_module.encode_texts(["q1", "q2"], mode="query")
    assert stub["value"].last_inputs == ["query: q1", "query: q2"]
    assert len(vecs) == 2


def test_encode_texts_mode_passage_applies_passage_prefix(stub):
    vecs = encoder_module.encode_texts(["p1", "p2"], mode="passage")
    assert stub["value"].last_inputs == ["passage: p1", "passage: p2"]
    assert len(vecs) == 2


def test_encode_texts_empty_list_returns_empty(stub):
    assert encoder_module.encode_texts([], mode="query") == []


def test_encode_texts_requires_mode():
    """Calling encode_texts without `mode=` must raise TypeError — prevents
    accidental silent query/passage mix-ups."""
    with pytest.raises(TypeError):
        encoder_module.encode_texts(["x"])  # type: ignore[call-arg]


def test_query_and_passage_vectors_differ(stub):
    """Sanity: encoding the same text as query vs passage yields different
    vectors (the prefix changes the embedding)."""
    q = encoder_module.encode_query("harnais chien")
    p = encoder_module.encode_passage("harnais chien")
    assert q != p
