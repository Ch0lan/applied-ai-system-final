"""Unit tests for the retrieval layer."""

import pytest

from src.retriever import (
    KnowledgeRetriever,
    RetrievalError,
    load_documents,
    parse_document,
    tokenize,
)

SOURCES = ["data/knowledge", "data/knowledge_user"]

SAMPLE = """---
id: sample-doc
title: A Sample Document
tags: alpha, beta gamma
genre: jazz
energy: 0.4
avoid_explicit: true
source_weight: 1.5
---

First paragraph of the body.

Second paragraph.
"""


@pytest.fixture(scope="module")
def retriever():
    return KnowledgeRetriever.from_directories(SOURCES)


def test_tokenize_drops_stopwords_and_short_tokens():
    assert tokenize("I want something for the gym at 6am") == ["gym", "6am"]


def test_parse_document_reads_front_matter_and_coerces_types():
    doc = parse_document(SAMPLE, source="test", fallback_id="fallback")
    assert doc.doc_id == "sample-doc"
    assert doc.tags == ["alpha", "beta gamma"]
    assert doc.cues["genre"] == "jazz"
    assert doc.cues["energy"] == 0.4
    assert doc.cues["avoid_explicit"] is True
    assert doc.source_weight == 1.5
    assert doc.snippet == "First paragraph of the body."


def test_parse_document_returns_none_without_front_matter():
    assert parse_document("# Just a heading\n\ntext", source="test", fallback_id="x") is None


def test_load_documents_indexes_both_sources():
    docs = load_documents(SOURCES)
    sources = {d.source for d in docs}
    assert sources == {"data/knowledge", "data/knowledge_user"}
    assert len(docs) >= 9


def test_empty_corpus_raises():
    with pytest.raises(RetrievalError):
        KnowledgeRetriever([])


def test_missing_directory_is_ignored_not_fatal():
    docs = load_documents(["data/knowledge", "data/does_not_exist"])
    assert docs


@pytest.mark.parametrize(
    "query,expected_doc",
    [
        ("i need to focus and study for my exam", "study-focus"),
        ("gym session, lifting heavy", "workout-high-intensity"),
        ("help me fall asleep", "sleep-winddown"),
        ("driving home on the highway at night", "commute-driving"),
        ("cooking dinner for guests", "dinner-background"),
    ],
)
def test_retrieval_puts_the_right_context_first(retriever, query, expected_doc):
    hits = retriever.retrieve(query, k=3)
    assert hits, "expected at least one hit for %r" % query
    assert hits[0][0].doc_id == expected_doc


def test_retrieval_returns_nothing_for_gibberish(retriever):
    assert retriever.retrieve("zzzz qqqq xxxx") == []


def test_retrieval_returns_nothing_for_stopwords_only(retriever):
    assert retriever.retrieve("the and of it") == []


def test_scores_are_sorted_descending(retriever):
    hits = retriever.retrieve("study session with no lyrics", k=4)
    scores = [score for _, score in hits]
    assert scores == sorted(scores, reverse=True)


def test_source_weight_boosts_personal_note(retriever):
    """The personal note declares source_weight > 1, so it outranks on its own topic."""
    hits = retriever.retrieve("late night coding on my side project", k=2)
    assert hits[0][0].doc_id == "personal-late-night-coding"
    assert hits[0][0].source_weight > 1.0
