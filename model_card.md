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
