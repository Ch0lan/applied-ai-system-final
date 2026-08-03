"""Unit tests for input validation and output critique."""

import pytest

from src.guardrails import (
    MAX_QUERY_CHARS,
    critique_recommendations,
    validate_query,
)


def song(title, artist="A", explicit=False, energy=0.5, language="english"):
    return {
        "title": title, "artist": artist, "explicit": explicit,
        "energy": energy, "language": language, "genre": "pop",
    }


def rec(*songs):
    return [(s, 1.0, "reason") for s in songs]


@pytest.mark.parametrize("query", ["", "   ", None])
def test_empty_input_rejected(query):
    result = validate_query(query)
    assert not result.ok and result.code == "EMPTY_INPUT"


def test_too_short_rejected():
    assert validate_query("hi").code == "TOO_SHORT"


def test_too_long_rejected():
    assert validate_query("study " * MAX_QUERY_CHARS).code == "TOO_LONG"


def test_non_language_rejected():
    assert validate_query("###!!!@@@ 12345 %%%").code == "NOT_LANGUAGE"


def test_crisis_language_routes_to_referral_not_a_playlist():
    result = validate_query("sad songs, i want to kill myself")
    assert not result.ok
    assert result.code == "OUT_OF_SCOPE"
    assert "988" in result.message


def test_ordinary_request_accepted():
    assert validate_query("something calm for studying").ok


def test_clean_output_has_no_violations():
    prefs = {"energy": 0.5, "avoid_explicit": False}
    assert critique_recommendations(rec(song("A", "X"), song("B", "Y")), prefs, 0.8, k=2) == []


def test_explicit_leak_detected():
    prefs = {"energy": 0.5, "avoid_explicit": True}
    codes = [v.code for v in critique_recommendations(
        rec(song("A", "X", explicit=True)), prefs, 0.8, k=1)]
    assert "EXPLICIT_LEAK" in codes


def test_language_enforced_only_when_the_user_said_it():
    prefs = {"energy": 0.5, "language": "spanish"}
    songs = rec(song("A", "X"), song("B", "Y"), song("C", "Z"))

    inferred = [v.code for v in critique_recommendations(songs, prefs, 0.8, k=3)]
    assert "LANGUAGE_MISS" not in inferred

    stated = [v.code for v in critique_recommendations(
        songs, prefs, 0.8, k=3, user_stated=["language"])]
    assert "LANGUAGE_MISS" in stated


def test_artist_crowding_detected():
    prefs = {"energy": 0.5}
    songs = rec(song("A", "X"), song("B", "X"), song("C", "X"))
    codes = [v.code for v in critique_recommendations(songs, prefs, 0.8, k=3)]
    assert "ARTIST_CROWDING" in codes


def test_energy_drift_detected():
    prefs = {"energy": 0.9}
    codes = [v.code for v in critique_recommendations(
        rec(song("A", "X", energy=0.2)), prefs, 0.8, k=1)]
    assert "ENERGY_DRIFT" in codes


def test_low_confidence_flagged():
    prefs = {"energy": 0.5}
    codes = [v.code for v in critique_recommendations(rec(song("A", "X")), prefs, 0.05, k=1)]
    assert "LOW_CONFIDENCE" in codes


def test_empty_result_short_circuits():
    violations = critique_recommendations([], {"energy": 0.5}, 0.8, k=5)
    assert [v.code for v in violations] == ["NO_RESULTS"]


def test_short_list_detected():
    prefs = {"energy": 0.5}
    codes = [v.code for v in critique_recommendations(rec(song("A", "X")), prefs, 0.8, k=5)]
    assert "SHORT_LIST" in codes
