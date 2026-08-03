"""Tests for the specialized explanation layer."""

import pytest

from src.explainer import Explainer, ExplanationStyle, StyleError, style_metrics

SONG = {
    "title": "Quiet Desk Lamp", "artist": "Paper Lanterns", "genre": "lofi",
    "mood": "focused", "language": "instrumental", "mood_tag": "calm", "energy": 0.33,
}

INTENSE = dict(SONG, genre="edm", mood="intense")


@pytest.fixture(scope="module")
def explainer():
    return Explainer()


def test_style_loads_phrase_table_and_exemplars():
    style = ExplanationStyle.load()
    assert style.phrases["genre match"]
    assert len(style.exemplars) >= 3


def test_missing_style_file_raises():
    with pytest.raises(StyleError):
        ExplanationStyle.load("data/style/nope.md")


def test_rendering_drops_score_arithmetic(explainer):
    out = explainer.render(SONG, "genre match (+1.0), mood match (+2.5), energy similarity (+0.92)")
    assert not any(ch.isdigit() for ch in out)
    assert "+" not in out


def test_rendering_addresses_the_listener(explainer):
    out = explainer.render(SONG, "genre match (+1.0), energy similarity (+0.92)")
    assert "you" in out.lower()


def test_rendering_substitutes_song_fields(explainer):
    assert "lofi" in explainer.render(SONG, "genre match (+1.0)")
    assert "instrumental" in explainer.render(SONG, "language match (+0.5)")


def test_article_agrees_with_the_substituted_word(explainer):
    out = explainer.render(INTENSE, "mood match (+2.5)")
    assert "an intense mood" in out
    assert "a intense" not in out


def test_qualifiers_are_moved_to_the_end(explainer):
    out = explainer.render(SONG, "artist diversity penalty (-1.0), genre match (+1.0)")
    assert out.index("lofi") < out.index("ranked down")


def test_penalty_only_reasons_still_render(explainer):
    out = explainer.render(SONG, "too acoustic for preference (-0.5)")
    assert "acoustic" in out
    assert out.endswith(".")


def test_length_is_capped(explainer):
    long_reasons = ", ".join([
        "genre match (+1.0)", "mood match (+2.5)", "energy similarity (+0.92)",
        "acoustic match (+0.5)", "language match (+0.5)", "popularity fit (+0.4)",
        "artist diversity penalty (-1.0)",
    ])
    assert len(explainer.render(SONG, long_reasons)) <= explainer.style.max_chars + 1


def test_empty_and_unparseable_reasons_fall_back(explainer):
    assert "closest" in explainer.render(SONG, "")
    assert "closest" in explainer.render(SONG, "no strong matches")


def test_rendering_is_deterministic(explainer):
    reasons = "genre match (+1.0), mood match (+2.5)"
    assert explainer.render(SONG, reasons) == explainer.render(SONG, reasons)


def test_style_metrics_separate_baseline_from_specialized(explainer):
    raw = ["genre match (+1.0), energy similarity (+0.92)"]
    styled = [explainer.render(SONG, raw[0])]
    base, spec = style_metrics(raw), style_metrics(styled)
    assert base["digit_share"] == 1.0 and spec["digit_share"] == 0.0
    assert base["second_person_share"] == 0.0 and spec["second_person_share"] == 1.0


def test_style_metrics_handle_empty_input():
    assert style_metrics([])["count"] == 0
