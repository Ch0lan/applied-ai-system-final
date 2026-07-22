# AI Interactions Log

> **Stretch features only.** This file documents the optional stretch features attempted in this project.

---

## Agentic Workflow (SF8) — Additional Song Attributes

**What task did you give the agent?**

Add 5+ new meaningful song attributes to `data/songs.csv` (beyond the original 9 columns) and wire them into the scoring logic in `src/recommender.py` so they actually affect recommendations, not just sit unused in the CSV.

**Prompts used:**

- "Add 5 new attributes to the song dataset that add real depth — something like popularity, release era, language, explicit flag, and a more granular mood tag than the existing `mood` column. Fill in plausible values for all 17 existing songs."
- "Now wire `popularity`, `mood_tag`, `language`, and `explicit` into `_score_components` as optional scoring terms, but keep the existing required `Song`/`UserProfile` dataclass fields untouched so `tests/test_recommender.py` doesn't break — new fields need defaults."

**What did the agent generate or change?**

- `data/songs.csv`: added `popularity` (0-100), `release_decade` (e.g. `2020s`, `1990s`, `1800s` for the classical track), `language` (`english` / `instrumental` / `korean`), `explicit` (bool), and `mood_tag` (a finer-grained mood descriptor like `pumped`, `wistful`, `serene`) for all 17 rows.
- `src/recommender.py`: added the 5 new fields to the `Song` dataclass with sensible defaults (so old test-file construction of `Song(...)` without the new fields still works), added matching optional preference fields to `UserProfile` (`favorite_mood_tag`, `favorite_language`, `target_popularity`, `avoid_explicit`), and extended `_score_components` with four new optional scoring terms: mood-tag match (+0.75), language match (+0.5), popularity closeness (up to +0.5), and an explicit-content penalty (-1.0) if the user opted to avoid it.
- `load_songs` updated to parse `popularity` as float and `explicit` as bool from the CSV string.

**What did you verify or fix manually?**

- Ran `pytest` after each change to confirm the two existing tests (which construct `Song`/`UserProfile` without any of the new fields) still pass — this required making all 5 new `Song` fields and all 4 new `UserProfile` fields have defaults, since dataclasses require non-default fields to come first.
- Manually checked that the new attribute values I filled in for the CSV are internally consistent (e.g. lofi/ambient/classical tracks marked `instrumental`, the k-pop track marked `korean`, only a handful of high-intensity tracks marked `explicit: True`) rather than accepting arbitrary AI-generated values without a sanity pass.

---

## Design Pattern (SF10) — Multiple Ranking Modes

**Which design pattern did you use?**

Strategy pattern: a `ScoringStrategy` dataclass holds a named set of weights (`genre_weight`, `mood_weight`, `energy_weight`), and a `STRATEGIES` dict maps mode names (`"balanced"`, `"genre-first"`, `"mood-first"`, `"energy-focused"`) to strategy instances. `score_song`, `recommend_songs`, and `Recommender.recommend`/`explain_recommendation` all accept a `mode: str` parameter that looks up the strategy and passes it into the shared `_score_components` function, which uses the strategy's weights instead of hardcoded constants.

**How did AI help you brainstorm or implement it?**

Asked: "I want a user to be able to switch between different ranking priorities — genre-first, mood-first, energy-focused — without duplicating the whole scoring function three times. What's the cleanest pattern for this in Python?" The agent suggested the Strategy pattern specifically because the "algorithm" here really is just a set of weights, so a lightweight dataclass-plus-dict registry avoids both code duplication and a heavier class-hierarchy-with-inheritance approach that would be overkill for four numbers.

**How does the pattern appear in your final code?**

`src/recommender.py`: the `ScoringStrategy` dataclass and `STRATEGIES` dict near the top of the file, consumed by `_score_components(..., strategy: ScoringStrategy)`. `src/main.py` demonstrates switching between all four modes for the same "High-Energy Pop" profile in the "Ranking mode comparison" section of its output — e.g. `mood-first` mode pushes *Rooftop Lights* (mood match, no genre match) ahead of *Gym Hero* (genre match, no mood match), which is the opposite order from `balanced` mode.
