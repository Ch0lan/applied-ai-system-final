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

---

# Module 5 — Agentic Workflow Enhancement (Resonance)

The Module 3 entries above documented me prompting an AI assistant while building. This section
documents the **system's own** multi-step reasoning: every run of `src/agent.py` plans, calls
tools, critiques its own output, and decides whether to revise. Traces are written to
`logs/traces/<run_id>.json` on every run, not just printed.

## The decision chain

```
validate_input          guardrail: empty / short / long / not-language / out-of-scope
      |
    plan                declare the tools and the revision budget
      |
   retrieve  (tool)     BM25 over 9 documents in 2 sources
      |
    ground   (tool)     merge retrieved cues + stated preferences -> profile + confidence
      |
  recommend  (tool)  <--------------------+
      |                                   |
   critique  (tool)                       |  revise: hard_filter_explicit
      |                                   |          hard_filter_language
      +-- violations, budget left --------+          enforce_diversity
      |                                              switch_to_energy_strategy
      +-- passed, or budget spent --> answer         broaden_retrieval
                                                     relax_constraints
```

## Trace 1 — two chained revisions, ending in an honest warning

Command: `python -m src.cli "korean music for the gym" --k 5 --trace`
Full JSON: [`logs/traces/example-korean-gym.json`](logs/traces/example-korean-gym.json)

```
Trace ef449f17 | query: 'korean music for the gym'
  1. validate_input         ok=True, code=, reason=
  2. plan                   tools=['retrieve', 'ground', 'rank', 'critique'], max_revisions=2
  3. retrieve               k=3, hits=['language-and-culture(3.99)', 'workout-high-intensity(3.68)', 'personal-late-night-coding(0.86)']
  4. ground                 prefs={'genre': '', 'mood': 'happy', 'energy': 0.781, 'likes_acoustic': False, 'avoid_explicit': False, 'language': 'korean'}, strategy=balanced
  5. recommend              attempt=1, strategy=balanced, pool=52, picks=['Paper Planes Over Kyoto', 'Seoul Rain Letter', 'Cherry Blossom Skyline', 'Block Party Dawn', ...]
  6. critique               attempt=1, passed=False, violations=['LANGUAGE_MISS']
  7. revise                 attempt=1, applied=['LANGUAGE_MISS -> restricted candidate pool to language=korean (4 left)']
  8. recommend              attempt=2, strategy=balanced, pool=4, picks=['Paper Planes Over Kyoto', 'Seoul Rain Letter', 'Cherry Blossom Skyline']
  9. critique               attempt=2, passed=False, violations=['SHORT_LIST']
  10. revise                 attempt=2, applied=['SHORT_LIST -> relaxed the genre constraint (4 candidates); kept language=korean']
  11. recommend              attempt=3, strategy=balanced, pool=4, picks=['Paper Planes Over Kyoto', 'Seoul Rain Letter', 'Cherry Blossom Skyline']
  12. critique               attempt=3, passed=False, violations=['SHORT_LIST']
  13. finalize               status=returned_with_warnings, revisions=2, unresolved=['SHORT_LIST']
```

Reading it: two documents disagreed (a language document and a workout document) and the merge
took `mood` from one and `energy` from the other. Attempt 1 returned mostly English tracks, so
the critic fired `LANGUAGE_MISS` and the agent hard-filtered the pool. Attempt 2 could only find
three tracks, so `SHORT_LIST` fired and the agent relaxed the *genre* constraint while
deliberately keeping the language filter — that ordering is the fix for a bug where relaxation
discarded the user's stated constraint. Attempt 3 could not do better; the catalog holds four
Korean tracks and the artist cap removes one. The run finalizes as
`returned_with_warnings` and the CLI prints the unresolved `SHORT_LIST` to the user.

## Trace 2 — the critic catching what the scorer let through

Command: `python -m src.cli "clean hip-hop for lifting" --k 4 --trace`

```
  1. validate_input         ok=True, code=, reason=
  2. plan                   tools=['retrieve', 'ground', 'rank', 'critique'], max_revisions=2
  3. retrieve               k=3, hits=['workout-high-intensity(7.15)']
  4. ground                 prefs={'genre': 'hip-hop', 'mood': 'intense', 'energy': 0.9, 'avoid_explicit': True}, strategy=energy-focused, confidence=0.89
  5. recommend              attempt=1, strategy=energy-focused, pool=52, picks=['Block Party Dawn', 'Storm Runner', 'Barbell Gospel', 'Kilometro Cero']
  6. critique               attempt=1, passed=False, violations=['EXPLICIT_LEAK']
  7. revise                 attempt=1, applied=['EXPLICIT_LEAK -> hard-filtered explicit tracks out of the candidate pool (45 left)']
  8. recommend              attempt=2, strategy=energy-focused, pool=45, picks=['Block Party Dawn', 'Storm Runner', 'Kilometro Cero', 'Thunder Gym Cycle']
  9. critique               attempt=2, passed=True, violations=[]
  10. finalize               status=passed_critique, revisions=1
```

The Module 3 scorer only subtracts 1.0 for an explicit track, which *Barbell Gospel* (hip-hop,
energy 0.89, explicit) absorbed on its energy score alone. Attempt 1 was never shown to the user; the critic caught it in the finished
list and the agent converted a soft penalty into a hard filter.

## Trace 3 — refusal before any tool call

Command: `python -m src.cli "zzzz qqqq wwww vvvv"`

```
  1. validate_input         ok=True, code=, reason=
  2. plan                   tools=['retrieve', 'ground', 'rank', 'critique'], max_revisions=2
  3. retrieve               k=3, hits=[]
  4. no_grounding
```

Retrieval returned nothing, so the run stops before grounding rather than inventing a profile
and answering confidently. Out-of-scope and malformed requests stop even earlier, at step 1.

## Where the traces are

- Every CLI run: `logs/traces/<run_id>.json` (disable with `--no-save-trace`)
- Every evaluation run: one trace per case, plus `logs/eval_report.md`
- All runs also append to `logs/run.log`
- A frozen example is committed at `logs/traces/example-korean-gym.json`
