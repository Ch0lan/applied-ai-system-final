# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

This version is a **content-based** recommender: it never looks at what other users liked (that's collaborative filtering, the approach behind Spotify's "Discover Weekly"). Instead it compares each song's own attributes against one user's stated taste profile and scores the match directly.

---

## How The System Works

Real platforms like Spotify and YouTube blend two approaches. **Collaborative filtering** looks at behavior across many users — "people who liked what you liked also liked this" — using data like plays, skips, and playlist co-occurrence. **Content-based filtering** (what this project builds) ignores other users entirely and instead compares a song's own attributes (genre, mood, tempo, energy) against one user's taste profile. Big platforms combine both plus engagement signals (skip rate, replay count, time of day) to rank a candidate pool; this simulation only does the content-based half, on a tiny hand-built catalog.

**`Song`** fields: `id`, `title`, `artist`, `genre`, `mood`, `energy` (0–1), `tempo_bpm`, `valence`, `danceability`, `acousticness` (0–1).

**`UserProfile`** stores: `favorite_genre`, `favorite_mood`, `target_energy` (0–1), `likes_acoustic` (bool).

**Algorithm Recipe** (the scoring rule, see `_score_components` in `src/recommender.py`):

- **+2.0** if the song's genre matches `favorite_genre` (exact match, case-insensitive)
- **+1.0** if the song's mood matches `favorite_mood`
- **up to +1.5** for energy similarity: `(1 - abs(song.energy - target_energy)) * 1.5` — this rewards songs *close* to the target, not just high-energy songs, so a target of `0.3` correctly favors a calm song over an intense one
- **±0.5** acoustic bonus/penalty (OOP path only): `+0.5` if `likes_acoustic` and `acousticness >= 0.6`, `-0.5` if the user dislikes acoustic and the song is acoustic anyway

Genre outweighs mood because genre is the strongest, most stable taste signal (a "pop fan" rarely means "rock, but happy"); mood is a secondary refinement. Energy uses a **similarity** score rather than a threshold so it can differentiate "chill lofi" from "intense rock" symmetrically around the user's target — a raw "higher energy = better" rule would rank every user's top song identically.

**Scoring vs. Ranking:** `score_song` (or `Recommender.explain_recommendation`) judges *one* song against the profile and returns a number plus reasons. `recommend_songs` (or `Recommender.recommend`) is the ranking rule — it has to run the scoring function over the *entire* catalog, then sort and slice to the top k. You need both: scoring answers "how good is this song for this user," ranking answers "which songs win against all the others."

**Expected bias:** genre match is worth 2x mood match, so this system will over-prioritize genre — a song that nails mood and energy but misses genre can still lose to a same-genre song that's a worse overall vibe fit. See `model_card.md` for the case this actually happened in testing.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Output of `python -m src.main`, default "High-Energy Pop" profile (`genre=pop, mood=happy, energy=0.8`):

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
```

Full output for all four test profiles, plus a ranking-mode comparison (`balanced`/`genre-first`/`mood-first`/`energy-focused`), is in `model_card.md` under Evaluation.

**Stretch features implemented:** 5 additional song attributes (`popularity`, `release_decade`, `language`, `explicit`, `mood_tag` — see `ai_interactions.md`), an artist-diversity penalty to reduce filter bubbles (see `model_card.md` § Fairness), 4 switchable ranking modes via a Strategy pattern (see `ai_interactions.md`), and `tabulate`-formatted table output above.

---

## Experiments You Tried

- **Weight shift:** halved `GENRE_WEIGHT` (2.0 → 1.0) and doubled `ENERGY_WEIGHT` (1.5 → 3.0) temporarily. Result: for "High-Energy Pop", *Gym Hero* (pop, intense, energy 0.93) jumped ahead of *Sunrise City* (pop, happy, energy 0.82) because the energy term now dominates even though *Sunrise City* also matches mood. This confirms genre/mood weighting, not just energy, is what keeps mood-matching songs competitive — reverted back to the original weights afterward.
- **Feature removal:** commented out the mood-match bonus. Result: for "Chill Lofi", *Focus Flow* (lofi, focused) tied much closer with *Midnight Coding* (lofi, chill) since mood no longer separated them — mood removal flattens differentiation *within* a genre, which is exactly the "intense rock vs. chill lofi" distinction the profile critique in Phase 2 worried about.
- **Adversarial profile:** added "Conflicted Listener" (`genre=metal, mood=sad, energy=0.9`) — no song in the catalog has mood `sad`, so every result relies on genre + energy only. The system doesn't break, it just quietly degrades to a 2-factor score, which is worth flagging as a limitation (see below).

---

## Limitations and Risks

- Catalog is tiny (17 songs) — real platforms score millions of tracks, so ranking noise here is much more visible than it would be at scale.
- Genre/mood are exact-string matches, not semantic ("r&b" and "rnb" would not match) — no fuzzy matching or genre taxonomy.
- It only understands the 4 audio-style features it scores on; it has no idea about lyrics, language, artist popularity, or listening history.
- Genre is weighted 2x mood, so it structurally over-favors genre — a great mood/energy fit in the "wrong" genre will usually lose to a mediocre same-genre song.
- If a user's mood has no match anywhere in the catalog (see "Conflicted Listener" above), the system silently falls back to genre+energy only, with no signal to the user that their mood preference had zero effect.

Deeper bias analysis is in `model_card.md`.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Building the scoring function made concrete something that's easy to hand-wave: a "prediction" here is just a weighted sum of exact-match flags and a similarity term, nothing more. There's no learning involved — the weights (2.0 genre, 1.0 mood, 1.5 energy) are hand-picked and immediately determine every ranking. That makes bias mechanical and inspectable: I could point to the exact line that causes genre to dominate mood, in a way you can't do with a trained model. The clearest place unfairness shows up is dataset composition — genres with more catalog entries (pop, lofi) get recommended more often across different profiles simply because they have more chances to score well, which is a miniature version of the popularity bias real platforms fight.



