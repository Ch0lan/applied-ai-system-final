# 🎧 Model Card: Resonance (Module 5) — formerly VibeFinder (Module 3)

> **Sections 10-14 are the Module 5 reflection** (AI collaboration, limitations and bias,
> misuse, testing surprises, retrieval impact). Sections 1-9 are the original Module 3 model
> card for VibeFinder 1.0, kept for provenance; where they describe a 17-song catalog and a
> caller-supplied profile, that is the *base project*, not the current system.

---

# Part A — Module 3 model card (VibeFinder 1.0, retained for provenance)

# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeFinder 1.0**

---

## 2. Intended Use

VibeFinder is a classroom simulation of a content-based music recommender. Given one user's stated taste profile (favorite genre, favorite mood, target energy, acoustic preference), it ranks a small song catalog and returns the top-k matches with a plain-language reason for each.

- Generates a ranked list of songs plus an explanation string for each recommendation — never a black-box score alone.
- Assumes the user can state their preferences directly as explicit values (genre/mood/energy), not inferred from listening history — there is no behavioral or collaborative signal at all.
- Built for classroom exploration of how recommender math works, not for real listeners. The catalog (17 songs) and scoring rule are far too small and simple for production use.

---

## 3. How the Model Works

Every song gets scored against the user's profile using a set of weighted rules, added together:

- **Genre match** is worth the most by default (2 points) — matching musical style is treated as the strongest taste signal.
- **Mood match** is worth 1 point — a secondary refinement on top of genre.
- **Energy closeness** is worth up to 1.5 points, and it's a *similarity* score, not a "bigger is better" score — a user who wants calm, low-energy music gets full credit for calm songs, not penalized for not picking the most intense track in the catalog.
- **Acoustic fit** adds half a point if the user likes acoustic music and the song is acoustic, or subtracts half a point if the user dislikes acoustic music and the song is acoustic anyway.
- **Mood-tag match** (a finer-grained mood word like "pumped" or "wistful") adds +0.75 when the user specifies one and it matches.
- **Language match** adds +0.5 when the user specifies a preferred language/vocal style and it matches.
- **Popularity fit** adds up to +0.5 the closer a song's popularity score is to a user's target popularity.
- **Explicit-content avoidance** subtracts 1 point if the user asked to avoid explicit content and the song is marked explicit — a content-safety filter, not a taste signal.

All songs get scored this way, then ranked highest-to-lowest with an artist-diversity guard (see Section 6) applied on top, and the top few are returned. Nothing here is learned from data — the weights were chosen by hand based on the assumption that genre and mood are more stable signals of taste than a single numeric feature like energy.

**Ranking modes (Strategy pattern):** the genre/mood/energy weights above are the `"balanced"` mode. Three alternate modes are available — `"genre-first"`, `"mood-first"`, `"energy-focused"` — each just a different set of the same three weights, selected via a `mode` argument on `recommend_songs`/`Recommender.recommend`. Switching modes visibly reorders results: e.g. `mood-first` mode ranks *Rooftop Lights* (mood match only) above *Gym Hero* (genre match only) for the "High-Energy Pop" profile, the opposite of `balanced` mode's order.

Change from starter logic: the starter shipped empty `TODO` stubs for `load_songs`, `score_song`, `recommend_songs`, and the `Recommender` class — all of this scoring/ranking logic, plus the CSV loader and the fix to `main.py`'s import (it referenced a bare `recommender` module that doesn't resolve under `python -m src.main`), was added from scratch.

---

## 4. Data

- **17 songs** in `data/songs.csv` (10 from the starter file, 7 added to broaden genre coverage).
- **14 attributes per song**: the original 9 (`genre`, `mood`, `energy`, `tempo_bpm`, `valence`, `danceability`, `acousticness`, `title`, `artist`) plus 5 added for the stretch feature — `popularity` (0-100), `release_decade`, `language`, `explicit` (bool), and `mood_tag` (a finer-grained mood descriptor).
- **Genres represented**: pop, lofi, rock, ambient, jazz, synthwave, indie pop, hip-hop, edm, country, metal, classical, r&b, k-pop — 14 genres across 17 songs, so most genres have exactly 1 song.
- Missing from the dataset: actual lyrics/song text, artist follower counts, cultural/regional genres beyond k-pop (e.g. reggaeton, afrobeats), and any behavioral data (plays, skips, likes) — this is a purely attribute-based catalog.

---

## 5. Strengths

- Clearly differentiates opposite-taste profiles: "Chill Lofi" and "Deep Intense Rock" produce almost entirely different top-5 lists (see Evaluation below), which matches intuition — the energy-similarity term is doing its job.
- Every recommendation ships a reason string built directly from the same math that produced the score, so nothing is generic or fabricated — "genre match (+2.0)" always literally means the genre string matched.
- Handles a user whose mood has zero catalog matches ("Conflicted Listener", mood=`sad`) without crashing — it just gracefully degrades to genre + energy only.

---

## 6. Limitations and Bias

The system over-prioritizes genre because it's weighted 2x mood — a song that's a near-perfect mood and energy fit but the "wrong" genre will often lose to a same-genre song that fits worse overall. Because 2 of 17 songs are pop and pop is the default demo profile, pop songs (*Sunrise City*, *Gym Hero*) show up near the top of several unrelated test runs just from having more genre chances to match — a small-scale version of the popularity bias that real platforms wrestle with. Exact-string genre/mood matching also means the model has zero fuzzy matching: a catalog with "rnb" instead of "r&b" would silently never match a "r&b" preference, with no error or warning. Finally, the acoustic bonus/penalty only exists in the OOP `Recommender` path, not the dict-based `recommend_songs` path used by `main.py` — the two pipelines are not fully feature-equivalent, which would confuse anyone extending only one of them.

---

## 7. Evaluation

Tested with 4 profiles via `python -m src.main`: **High-Energy Pop**, **Chill Lofi**, **Deep Intense Rock**, and an adversarial **Conflicted Listener** (`genre=metal, mood=sad, energy=0.9` — no song in the catalog has mood `sad`). Output below uses the `tabulate`-formatted table (Stretch Feature SF12).

```
Loading songs from data/songs.csv...
Loaded songs: 17

=== High-Energy Pop | mode=balanced | prefs: {'genre': 'pop', 'mood': 'happy', 'energy': 0.8} ===

+------------------------+---------------+---------+------------------------------------------------------------------+
| Title                  | Artist        |   Score | Reasons                                                          |
+========================+===============+=========+==================================================================+
| Sunrise City           | Neon Echo     |    4.47 | genre match (+2.0), mood match (+1.0), energy similarity (+1.47) |
+------------------------+---------------+---------+------------------------------------------------------------------+
| Gym Hero               | Max Pulse     |    3.3  | genre match (+2.0), energy similarity (+1.30)                    |
+------------------------+---------------+---------+------------------------------------------------------------------+
| Rooftop Lights         | Indigo Parade |    2.44 | mood match (+1.0), energy similarity (+1.44)                     |
+------------------------+---------------+---------+------------------------------------------------------------------+
| Cherry Blossom Skyline | Yuna Prism    |    1.5  | energy similarity (+1.50)                                        |
+------------------------+---------------+---------+------------------------------------------------------------------+
| Storm Runner           | Voltline      |    1.33 | energy similarity (+1.33)                                        |
+------------------------+---------------+---------+------------------------------------------------------------------+

=== Chill Lofi | mode=balanced | prefs: {'genre': 'lofi', 'mood': 'chill', 'energy': 0.35} ===

+---------------------+----------------+---------+--------------------------------------------------------------------------------+
| Title               | Artist         |   Score | Reasons                                                                        |
+=====================+================+=========+================================================================================+
| Library Rain        | Paper Lanterns |    4.5  | genre match (+2.0), mood match (+1.0), energy similarity (+1.50)               |
+---------------------+----------------+---------+--------------------------------------------------------------------------------+
| Midnight Coding     | LoRoom         |    4.39 | genre match (+2.0), mood match (+1.0), energy similarity (+1.40)               |
+---------------------+----------------+---------+--------------------------------------------------------------------------------+
| Focus Flow          | LoRoom         |    2.42 | genre match (+2.0), energy similarity (+1.42), artist diversity penalty (-1.0) |
+---------------------+----------------+---------+--------------------------------------------------------------------------------+
| Spacewalk Thoughts  | Orbit Bloom    |    2.4  | mood match (+1.0), energy similarity (+1.40)                                   |
+---------------------+----------------+---------+--------------------------------------------------------------------------------+
| Coffee Shop Stories | Slow Stereo    |    1.47 | energy similarity (+1.47)                                                      |
+---------------------+----------------+---------+--------------------------------------------------------------------------------+

=== Deep Intense Rock | mode=balanced | prefs: {'genre': 'rock', 'mood': 'intense', 'energy': 0.9} ===

+-------------------+--------------+---------+------------------------------------------------------------------+
| Title             | Artist       |   Score | Reasons                                                          |
+===================+==============+=========+==================================================================+
| Storm Runner      | Voltline     |    4.48 | genre match (+2.0), mood match (+1.0), energy similarity (+1.48) |
+-------------------+--------------+---------+------------------------------------------------------------------+
| Gym Hero          | Max Pulse    |    2.46 | mood match (+1.0), energy similarity (+1.46)                     |
+-------------------+--------------+---------+------------------------------------------------------------------+
| Bass Drop Odyssey | Volt Circuit |    1.43 | energy similarity (+1.43)                                        |
+-------------------+--------------+---------+------------------------------------------------------------------+
| Iron Requiem      | Grave Chorus |    1.4  | energy similarity (+1.40)                                        |
+-------------------+--------------+---------+------------------------------------------------------------------+
| Sunrise City      | Neon Echo    |    1.38 | energy similarity (+1.38)                                        |
+-------------------+--------------+---------+------------------------------------------------------------------+

=== Conflicted Listener | mode=balanced | prefs: {'genre': 'metal', 'mood': 'sad', 'energy': 0.9} ===

+-------------------+--------------+---------+-----------------------------------------------+
| Title             | Artist       |   Score | Reasons                                       |
+===================+==============+=========+===============================================+
| Iron Requiem      | Grave Chorus |    3.4  | genre match (+2.0), energy similarity (+1.40) |
+-------------------+--------------+---------+-----------------------------------------------+
| Storm Runner      | Voltline     |    1.48 | energy similarity (+1.48)                     |
+-------------------+--------------+---------+-----------------------------------------------+
| Gym Hero          | Max Pulse    |    1.46 | energy similarity (+1.46)                     |
+-------------------+--------------+---------+-----------------------------------------------+
| Bass Drop Odyssey | Volt Circuit |    1.43 | energy similarity (+1.43)                     |
+-------------------+--------------+---------+-----------------------------------------------+
| Sunrise City      | Neon Echo    |    1.38 | energy similarity (+1.38)                     |
+-------------------+--------------+---------+-----------------------------------------------+
```

**Profile comparisons:**

- **High-Energy Pop vs. Chill Lofi**: completely disjoint top-5s — the pop profile surfaces high-tempo, happy tracks (*Sunrise City*, *Gym Hero*) while the lofi profile surfaces slow, chill tracks (*Library Rain*, *Midnight Coding*). This is the energy-similarity term working exactly as designed: it isn't "higher energy wins," it's "closer to target wins," so a `target_energy=0.35` correctly favors calm songs over intense ones.
- **Deep Intense Rock vs. Conflicted Listener**: both want `energy≈0.9`, but Deep Intense Rock also has a real mood match (*Storm Runner*, mood=`intense`) pushing it to 4.48, while Conflicted Listener's `mood=sad` matches nothing in the catalog, so its best song (*Iron Requiem*, genre match only) tops out at 3.40. Same energy target, but the missing mood match costs a full point off the top score — this is the adversarial case surfacing a real limitation (see Section 6): mood having no match doesn't error, it just silently reduces every score by ~1 point.
- **Surprise**: *Gym Hero* (pop, intense, high energy) appears in the top 5 for **three of the four** profiles — Pop, Rock, and Conflicted Listener — purely because its high energy (0.93) scores well against any high `target_energy`, even when genre and mood don't match at all. In plain terms: "Gym Hero" keeps showing up for "Happy Pop" fans not because it understands their taste, but because it's a loud, high-energy song, and high energy alone is enough to score positively against almost any energetic profile — a good illustration of how a single dominant feature can masquerade as broad appeal.
- **Diversity penalty in action**: for "Chill Lofi", *Focus Flow* and *Midnight Coding* are both by artist `LoRoom`. Without a diversity guard, both would rank purely by score (4.39 and 3.42 for Focus Flow, ahead of other artists). With the guard, once *Midnight Coding* is selected, *Focus Flow*'s effective score drops by 1.0 (`3.42 → 2.42`), and it's re-ranked accordingly — the reason string now shows `artist diversity penalty (-1.0)` so the user can see why. A parallel effect happens in "High-Energy Pop": *Night Drive Loop* (same artist as #1 *Sunrise City*, `Neon Echo`) drops out of the top 5 entirely in favor of *Storm Runner*, a different artist with a lower raw score.
- **Ranking modes**: switching the same "High-Energy Pop" profile from `balanced` to `mood-first` mode flips the #2 and #3 spots — *Rooftop Lights* (mood match, no genre match) jumps from 3rd to 2nd, ahead of *Gym Hero* (genre match, no mood match), because mood is now weighted 2.5x instead of genre's 1x. This is the clearest possible demonstration that "genre-first" vs. "mood-first" isn't just a label — it changes real output order.

---

## 8. Future Work

- Add fuzzy/synonym matching for genre and mood (e.g. "rnb" ↔ "r&b", "sad" ↔ "melancholy") so small catalog inconsistencies don't silently zero out a match.
- Extend the artist-diversity guard (Section 6) to also cap genre repetition, not just artist repetition — right now two different-artist songs of the same genre can still fill an entire top-5.
- Let a user combine ranking modes (e.g. a custom weight blend) instead of picking one of four presets.

---

## Fairness / Diversity Component

To reduce "filter bubble" risk — one artist dominating every recommendation — the ranker (both `recommend_songs` and `Recommender.recommend`) applies a greedy **artist diversity penalty**: after each pick, any remaining song by an already-picked artist gets docked 1.0 point per prior pick by that artist before the next pick is chosen. This doesn't block repeat artists outright (a truly dominant song can still survive the penalty), but it stops a single prolific artist from mechanically sweeping the whole top-k just by having the most catalog entries. See the "Diversity penalty in action" bullet in Section 7 for a concrete before/after example (*Focus Flow* dropping from a same-artist runner-up to a penalized 3rd place behind a different-artist song).

---

## 9. Personal Reflection

The biggest learning moment was watching *Gym Hero* show up as a top-5 result for three unrelated profiles — it made concrete how a single dominant numeric feature (energy) can fake broad relevance even with zero genre or mood match, which is a small-scale preview of how real engagement-optimized feeds can over-recommend "safe," high-signal content. Using AI accelerated writing the CSV loader and the scoring/ranking boilerplate, but I had to double-check the actual weight values and the energy-similarity formula myself, since those are judgment calls (how much should genre outweigh mood?) that the AI can suggest but shouldn't decide alone. What surprised me most is how "smart" a completely hand-weighted, non-learned linear formula can feel — four numbers and a sort call produce results that read as genuinely tasteful for on-target profiles, which is a useful reminder that "personalization" doesn't require anything more sophisticated than a well-chosen scoring rule at small scale.

---

# Part B — Module 5 model card (Resonance)

## 10. What Changed From the Base Project

**Base project:** `ai110-module3show-musicrecommendersimulation-starter` (VibeFinder 1.0, Part A
above) — a content-based recommender that scored a 17-song catalog against a `UserProfile` the
caller supplied as explicit numeric values, and returned the top-k with reason strings.

**Resonance** keeps that scoring rule byte-for-byte (`src/recommender.py`) and adds the pipeline
around it:

- a BM25 retrieval layer over nine listening-context documents in two sources (`src/retriever.py`)
- a grounding layer that turns a sentence plus retrieved documents into the profile the scorer
  needs, with a confidence score and full provenance per cue (`src/profile_builder.py`)
- input validation and a seven-check output critic (`src/guardrails.py`)
- an agent loop that revises its own answer up to twice before showing it (`src/agent.py`)
- persisted reasoning traces and a run log (`src/trace.py`)
- an evaluation harness that writes a report (`src/evaluate.py`)
- a catalog grown from 17 to 52 songs across 5 languages

**Intended use is unchanged in spirit and unchanged in scope:** a coursework demonstration of
how retrieval, grounding, and self-checking fit together. It is not a product, the catalog is
hand-written, and no listener has evaluated the taste of its output.

## 11. What are the limitations or biases in your system?

**Corpus coverage is the ceiling on everything.** Nine documents define every situation the
system understands. A request outside them either refuses (`NO_GROUNDING`) or, worse, retrieves
the *nearest* document and answers confidently from the wrong context. The refusal is visible;
the near-miss is not, and it is the failure mode I trust least.

**Lexical retrieval biases toward my vocabulary.** BM25 matches words, not meaning, so "I need
to zone in" fails where "focus" succeeds. The tags encode how *I* phrase things, in English.
A user of another dialect — or another language — gets worse retrieval for identical intent,
and the system will not know that happened.

**The knowledge documents are opinions written as facts.** "Instrumental music is better for
studying" and "sad listeners want mood-congruent music" are defensible generalizations that are
wrong for plenty of individuals. Because those documents now *drive* the profile rather than
merely describe it, my generalizations are enforced on every user who does not explicitly
contradict them. The `overrides` mechanism is the mitigation: anything the listener states
outright wins and is labelled in the output. It only helps listeners who know to state it.

**Catalog composition bias, inherited and amplified.** 52 hand-written songs cannot represent a
genre, a language, or a culture. English tracks outnumber every other language; Spanish, Korean,
and Japanese have 4-6 tracks each, which is why "korean music for the gym" cannot fill a
5-song request. Non-English requests will look worse to users than English ones for a reason
that has nothing to do with the algorithm.

**A stated genre is not enforced the way a stated language is.** Asking for "classical for a
workout" returns zero classical tracks: the workout document's energy target wins, and genre
stays a soft +1.0 scoring term. Language became a hard filter because a language mismatch makes
a recommendation useless; genre did not, and the result is an inconsistency a user can feel —
their words were honored in one dimension and quietly outvoted in another. The only signal they
get is a low confidence score (0.38 for that request).

**Confidence is not calibrated.** It is a weighted heuristic over retrieval strength, document
agreement, and how much the user stated. It usefully orders "well-grounded" against "shaky", and
it drives the `LOW_CONFIDENCE` check, but 0.71 does not mean 71% correct and should never be
shown to a user as if it did.

**Popularity is still in the scorer.** Inherited from Module 3, and the
`language-and-culture` document explicitly warns that popularity weighting buries non-English
catalogs. The current system does not lower that weight for language-specific requests — a known
gap between what my own corpus says and what my code does.

## 12. Retrieval Impact (before / after)

Measured by `python -m src.evaluate --compare`. "Context fit" is the share of returned tracks
whose energy is within ±0.2 of the target *and* whose genre or mood matches the situation.

| Request | Ungrounded baseline | Retrieval-grounded | Delta |
|---|---|---|---|
| something calm for studying, no lyrics | 0% | 80% | +80 pts |
| gym session, need something loud and hype | 60% | 100% | +40 pts |
| cooking dinner for guests, keep it in the background | 0% | 80% | +80 pts |
| help me fall asleep, nothing with singing | 0% | 60% | +60 pts |

Concretely, for *"something calm for studying, no lyrics"*:

- **Without retrieval** (`src/baseline.py`, popularity rank — what the base project does with no
  profile): *Bass Drop Odyssey* (edm, energy 0.95), *Gym Hero* (pop, energy 0.93, explicit),
  *Thunder Gym Cycle* (edm, 0.94), *Cherry Blossom Skyline* (k-pop, 0.80), *Sunrise City* (pop, 0.82). Every track is wrong, and one
  is explicit in a request that implies a shared study space.
- **With retrieval**: *Quiet Desk Lamp*, *Focus Flow*, *Signal From Europa*, *Deadline Sprint*,
  *Glass Ballroom* — all instrumental, all energy 0.26-0.44, none explicit.

The multi-source part matters too: `data/knowledge_user/personal-notes.md` carries
`source_weight: 1.25`, so "late night coding on my side project" retrieves the personal note
above the general study document and produces energy 0.42 rather than 0.35 — the note's whole
point ("steady momentum" rather than "minimum stimulus") reaching the output.

## 13. Could your AI be misused, and how would you prevent that?

**Emotional targeting.** A system that reads a mood from a sentence and picks music to match it
is one small step from a system that picks music to *keep* someone in that mood. The
`sad-catharsis` document deliberately supports mood-congruent listening — that is the honest
thing for ordinary sadness — but the same mechanism could be tuned for engagement rather than
for the listener. Constraint: there is no engagement signal anywhere in the system. It has no
memory across runs, no play/skip feedback, and nothing to optimize toward. Preserving that
absence matters more than any filter I could add.

**Crisis requests.** Emotional language is exactly what someone in crisis produces, and a
playlist is the wrong response. `validate_query` matches crisis phrasing before any retrieval
runs and returns a referral (988 in the US) instead of recommendations. It is a keyword filter:
it will miss indirect phrasing, and it will occasionally refuse a song lyric quoted as a request.
I chose the false-positive direction deliberately — a wrongly refused playlist costs a listener
one retry.

**Content exposure.** Explicit tracks are scored down, and hard-filtered out when the listener
asks for clean. The `EXPLICIT_LEAK` check exists because scoring alone provably leaked: two
explicit hip-hop tracks survived the −1.0 penalty on energy score. Nothing here verifies the
`explicit` flag itself, which is hand-labelled in the CSV.

**Overtrust in the explanations.** Every answer names the documents it used and shows the
per-song arithmetic, which makes the system feel more authoritative than nine markdown files
deserve. The mitigations are the visible confidence score, the printed unresolved warnings, and
the refusal paths — the system is built to look uncertain when it is.

## 14. How I collaborated with AI, and what surprised me while testing reliability

### How I used AI during development

I worked with Claude throughout: designing the layer boundaries (retriever /
grounding / guardrails / agent, so each is testable alone), drafting the BM25 implementation and
the knowledge corpus, writing test cases, and reviewing traces when the output looked wrong.
The debugging loop was the most valuable part — I would paste a trace showing the wrong document
winning retrieval, and we would work backwards to whether the cause was the corpus, the weights,
or the merge rule.

### One helpful AI suggestion

When I described the guardrails as input-validation only, the
suggestion was to make the critic run on the *finished recommendation list* and emit a fix code
per violation, so the agent could map codes to concrete revision actions. That is what turned
this from a pipeline into an agent: `EXPLICIT_LEAK → hard_filter_explicit` is the reason
"clean hip-hop for lifting" returns zero explicit tracks even though the Module 3 scorer alone
lets two through. Nothing in the original design would have caught that.

### One flawed AI suggestion

The first cue-merge implementation took every front-matter field from
retrieved documents and treated them all as hard constraints of equal standing. It looked
principled and produced a bug I did not see until I read a trace: for "gym session, loud and
hype", my personal coding note outranked the workout document, so `language: instrumental` — a
cue the listener never asked for — became a hard filter that cut the candidate pool down to the catalog's
instrumental tracks only for a gym request. The suggestion was wrong because it flattened a real
distinction. The fix was structural: `critique_recommendations` now takes `user_stated`, and
only preferences the listener expressed in their own words are enforced as filters; retrieved
cues stay soft scoring signals. A related version of the same mistake hit `relax_constraints`,
which "helpfully" restored the full catalog after a short list and discarded the Spanish filter
a Spanish speaker had explicitly asked for.

### What surprised me while testing reliability

Three things.

First, **the self-correcting agent was easier to get working than the retriever was to get
right.** The loop worked on the first run; the corpus took four rounds of tuning. Nearly every
real failure was a retrieval failure wearing a reasoning failure's clothes — a missing `asleep`
tag, an ambiguous `sprint` tag, a source weight 0.35 too high. The intelligence of the system
lives in the documents, not in the loop over them.

Second, **a self-correction can make the answer worse**, and it will look like a success in the
logs. The `relax_constraints` bug printed a confident "relaxed genre constraint" line while
quietly deleting the user's language filter. A critic that can revise needs its revisions
checked as carefully as its original answers.

Third, **10/10 passing means less than it looks like**, because I wrote the cases after watching
the system run. The suite is a strong regression guard and weak evidence of quality. The four
bugs above were found by reading traces and by tests that failed for reasons I did not
anticipate — not by the green summary line.

## 15. Future improvements

- Swap or supplement BM25 with sentence embeddings so paraphrases stop falling into
  `NO_GROUNDING`, and measure the change with the existing `--compare` harness.
- Lower the popularity weight on language-specific requests, which is what my own
  `language-and-culture` document already argues for.
- Calibrate confidence against human judgments rather than internal retrieval signals.
- Have real listeners rate the top-5 for a set of requests — the one thing no amount of
  self-critique can substitute for.

## 16. Specialization: baseline vs specialized output

The system has no generative model, so this is not a fine-tune. It is the brief's other
specialization option — **constrained tone and style driven by few-shot patterns** — implemented
as a data-file style contract in `data/style/explanation_style.md`: a phrase table, six explicit
style constraints, and four worked `raw → styled` exemplars that `src/explainer.py` follows
deterministically. Editing that markdown file changes every explanation the system emits without
touching code. `--plain` returns the baseline; `python -m src.evaluate --style` measures both.

Measured over the 20 explanations produced for the four comparison requests:

| Metric | Baseline (raw scorer, Module 3) | Specialized (exemplar-constrained) |
|---|---|---|
| explanations compared | 20 | 20 |
| mean characters | 83 | 82 |
| contain score arithmetic | 100% | 0% |
| address the listener directly | 0% | 100% |

Same songs, same underlying arithmetic, essentially the same length — the difference is entirely
in the voice:

| Request → song | Baseline | Specialized |
|---|---|---|
| studying → *Quiet Desk Lamp* | `genre match (+1.0), mood match (+2.5), energy similarity (+0.92), too acoustic for preference (-0.5), language match (+0.5)` | The lofi you asked for, and it lands in a focused mood - a little more acoustic than you usually go. |
| gym → *Thunder Gym Cycle* | `genre match (+1.0), mood match (+0.5), energy similarity (+2.88)` | The edm you asked for, and it lands in an intense mood. |
| dinner → *Coffee Shop Stories* | `genre match (+1.0), mood match (+2.5), energy similarity (+0.99), acoustic match (+0.5)` | The jazz you asked for, and it lands in a relaxed mood. |

The constraint that mattered most was "never claim a match the score did not actually contain".
The styled sentence is assembled *from the score components*, so it cannot describe a genre match
that did not happen — the failure mode of writing explanations separately from the ranking, where
the prose drifts away from what the system actually did. The visible cost is compression: the
style caps at two supporting clauses plus one qualifier, so the studying example silently drops
`language match`. That is a real loss of information, which is why `--plain` exists.
