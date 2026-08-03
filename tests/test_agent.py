"""Integration tests for profile grounding and the agent loop."""

import json

import pytest

from src.agent import RecommenderAgent
from src.profile_builder import build_profile
from src.retriever import KnowledgeRetriever

SOURCES = ("data/knowledge", "data/knowledge_user")


@pytest.fixture(scope="module")
def agent():
    return RecommenderAgent(knowledge_dirs=SOURCES)


@pytest.fixture(scope="module")
def retriever():
    return KnowledgeRetriever.from_directories(SOURCES)


# -- grounding ---------------------------------------------------------------

def test_profile_comes_from_retrieved_documents(retriever):
    hits = retriever.retrieve("i need to concentrate on my essay", k=3)
    profile = build_profile("i need to concentrate on my essay", hits)
    assert profile.prefs["mood"] == "focused"
    assert profile.prefs["energy"] < 0.5
    assert profile.evidence[0][0] == "study-focus"


def test_stated_preference_overrides_retrieved_cue(retriever):
    query = "studying but give me high energy metal"
    profile = build_profile(query, retriever.retrieve(query, k=3))
    assert profile.prefs["genre"] == "metal"
    assert profile.prefs["energy"] == 0.9
    assert profile.provenance["genre"] == "user request"
    assert "genre" in profile.overrides


def test_no_retrieval_means_no_confidence():
    profile = build_profile("anything", [])
    assert profile.confidence == 0.0
    assert profile.evidence == []


def test_confidence_rises_with_a_strong_specific_match(retriever):
    vague = build_profile("music please", retriever.retrieve("music please", k=3))
    specific_q = "clean hip-hop for lifting at the gym"
    specific = build_profile(specific_q, retriever.retrieve(specific_q, k=3))
    assert specific.confidence > vague.confidence


# -- agent loop --------------------------------------------------------------

def test_end_to_end_run_returns_k_songs(agent):
    result = agent.run("something calm for studying, no lyrics", k=5)
    assert result.ok
    assert len(result.recommendations) == 5
    assert result.profile.confidence > 0.3


def test_run_is_deterministic(agent):
    a = agent.run("gym session, loud and hype", k=4)
    b = agent.run("gym session, loud and hype", k=4)
    assert [s["title"] for s, _, _ in a.recommendations] == [s["title"] for s, _, _ in b.recommendations]


def test_agent_self_corrects_an_explicit_leak(agent):
    result = agent.run("clean hip-hop for lifting", k=4)
    assert any("hard-filtered explicit" in r for r in result.revisions), result.revisions
    assert all(not s["explicit"] for s, _, _ in result.recommendations)


def test_agent_honours_a_stated_language(agent):
    result = agent.run("spanish music for a road trip", k=4)
    languages = {s["language"] for s, _, _ in result.recommendations}
    assert languages == {"spanish"}


def test_agent_never_exceeds_the_artist_cap(agent):
    result = agent.run("lofi for focus", k=6)
    counts = {}
    for song, _, _ in result.recommendations:
        counts[song["artist"]] = counts.get(song["artist"], 0) + 1
    assert max(counts.values()) <= 2


def test_invalid_input_refuses_without_recommending(agent):
    result = agent.run("", k=5)
    assert not result.ok
    assert result.refusal_code == "EMPTY_INPUT"
    assert result.recommendations == []


def test_ungroundable_request_refuses_instead_of_guessing(agent):
    result = agent.run("zzzz qqqq wwww", k=5)
    assert not result.ok
    assert result.refusal_code == "NO_GROUNDING"


def test_trace_records_every_stage(agent):
    result = agent.run("dinner with guests", k=3)
    names = [step.name for step in result.trace.steps]
    for expected in ("validate_input", "plan", "retrieve", "ground", "recommend", "critique", "finalize"):
        assert expected in names


def test_result_is_json_serialisable(agent):
    result = agent.run("night drive", k=3)
    json.dumps(result.as_dict(), default=str)


def test_missing_catalog_raises_a_clear_error():
    with pytest.raises(FileNotFoundError):
        RecommenderAgent(catalog_path="data/nope.csv", knowledge_dirs=SOURCES)
