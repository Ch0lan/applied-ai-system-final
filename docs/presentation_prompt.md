# Presentation generation prompt

Paste everything below the line into a slide-generating AI (Gamma, Claude, ChatGPT, Copilot in
PowerPoint, etc.). Every fact in it is verified against the committed repo — the generator must
not invent numbers.

---

You are building a **10-slide deck for a 5-7 minute spoken presentation** for a university
applied-AI course final project. Produce (a) the slides and (b) speaker notes for each slide with
a target time in seconds. Total spoken time must land between 5:00 and 7:00 at ~140 words/minute,
so keep total speaker notes to roughly **800-950 words**.

## Hard rules

- **Do not invent any numbers, file names, or results.** Every figure you need is given below. If
  something is not in this prompt, leave it out.
- Slides carry **at most 6 bullet lines, at most 12 words per line**. The detail lives in the
  speaker notes, not on the slide.
- Use **monospace** for file paths, commands, and code output.
- No stock photos, no clip art, no gradient-heavy templates. Clean, technical, high contrast.
- Tone: an engineer explaining a system to other engineers. Direct, specific, no hype words
  ("revolutionary", "cutting-edge", "seamless", "leverage"). Do not use em dashes.
- Include the two failure findings and the two "partial" evaluation results. The honest failures
  are the strongest part of this project and must not be edited out.

## Design spec

- 16:9. Dark slate background (#12151A), off-white text (#EDEFF2), one accent color (#7FB069,
  a muted green) used only for section labels, key numbers, and diagram highlights.
- Title font: a geometric sans (Inter, Poppins, or similar), 40-44pt. Body 20-24pt.
- Code and output blocks: JetBrains Mono or similar, 16-18pt, on a slightly lighter panel
  (#1B1F26), left aligned, never centered.
- Each slide has a small top-left section label in the accent color (e.g. "02 / THE PROBLEM").
- Slide numbers bottom right. No footer clutter.

## Project facts (authoritative — use only these)

**Project name:** Resonance
**Repo:** https://github.com/Ch0lan/applied-ai-system-final
**Base project being extended:** `ai110-module3show-musicrecommendersimulation-starter`, a
Module 3 content-based music recommender ("VibeFinder 1.0"). It scored a 17-song CSV catalog
against a user profile the caller supplied as explicit numeric values (favorite genre, favorite
mood, target energy, acoustic preference) and returned the top-k songs with a plain-language
reason string for each. It had four switchable ranking strategies and an artist-diversity
penalty, and it ran as a fixed demo over four hard-coded profiles.

**The gap that motivated the extension:** the user had to already know their own taste as
numbers. You could not ask it for music, you had to hand it
`{"genre": "lofi", "mood": "chill", "energy": 0.35}`. It also had no way to tell whether its own
answer was any good.

**What Resonance adds, in one line each:**
- `src/retriever.py` — BM25 index over 9 listening-context documents in 2 sources
- `src/profile_builder.py` — turns a sentence plus retrieved documents into the scoring profile,
  with a confidence score and per-cue provenance
- `src/guardrails.py` — 5 input checks, 7 output checks
- `src/agent.py` — plan, retrieve, ground, recommend, critique, revise (2-revision budget,
  6 revision actions)
- `src/explainer.py` — renders the scorer's arithmetic in a constrained voice defined by
  few-shot exemplars in `data/style/explanation_style.md`
- `src/trace.py` — JSON reasoning trace per run, plus a run log
- `src/evaluate.py` — 10-case evaluation harness that writes `logs/eval_report.md`
- `src/recommender.py` — the Module 3 scorer, unchanged, still passing its original tests
- Catalog grown from 17 to 52 songs across 5 languages

**Everything runs locally.** No API key, no network call, no external model. Setup is
`pip install -r requirements.txt` (tabulate, pytest).

**Verified results:**
- 60/60 tests pass (`python -m pytest -q`)
- 10/10 evaluation cases pass, 28 criteria, mean confidence 0.71
- Retrieval impact (share of returned tracks that fit the situation), ungrounded baseline vs
  retrieval-grounded: studying 0% → 80%, gym 60% → 100%, dinner 0% → 80%, sleep 0% → 60%
- Specialization: explanations containing score arithmetic 100% → 0%, explanations that address
  the listener 0% → 100%, mean length essentially unchanged (83 → 82 characters)

**Verified demo output to reproduce on slides (do not alter):**

Request: `python -m src.cli "clean hip-hop for lifting" --k 4`

```
Grounded in: workout-high-intensity (7.15)
Profile: genre=hip-hop mood=intense energy=0.90 avoid_explicit=True strategy=energy-focused
Confidence: 0.89
Stated by you (overrode retrieval): avoid_explicit, genre

Self-corrections:
  - EXPLICIT_LEAK -> hard-filtered explicit tracks out of the candidate pool (45 left)
```

Trace for that run:

```
  5. recommend   attempt=1, pool=52, picks=['Block Party Dawn', 'Storm Runner', 'Barbell Gospel', ...]
  6. critique    attempt=1, passed=False, violations=['EXPLICIT_LEAK']
  7. revise      attempt=1, applied=['EXPLICIT_LEAK -> hard-filtered explicit tracks (45 left)']
  8. recommend   attempt=2, pool=45, picks=['Block Party Dawn', 'Storm Runner', 'Kilometro Cero', ...]
  9. critique    attempt=2, passed=True, violations=[]
  10. finalize   status=passed_critique, revisions=1
```

Why this matters: the Module 3 scorer only subtracts 1.0 for an explicit track, and
*Barbell Gospel* (hip-hop, energy 0.89, explicit) absorbed that penalty on its energy score.
The critic caught it in the finished list. Attempt 1 was never shown to the user.

Refusal example:

```
$ python -m src.cli "zzzz qqqq wwww vvvv"
REFUSED [NO_GROUNDING]
Nothing in the listening-context knowledge base matched that request...
```

Honest-shortfall example (`"korean music for the gym"`): two chained revisions
(`LANGUAGE_MISS` then `SHORT_LIST`), then the system returns 3 tracks and prints
`WARNING [SHORT_LIST] asked for 5 songs, got 3` instead of padding with English songs.

**The two real bugs to present (both found by reading traces, not by tests):**
1. *An inferred preference was enforced as if the user had stated it.* For "gym session, loud and
   hype", a personal note outranked the workout document, so `language: instrumental` — which the
   listener never asked for — became a hard filter on a gym request. Fix was structural: the
   critic now takes `user_stated`, and only preferences the listener expressed in their own words
   become hard filters. Retrieved cues stay soft scoring signals.
2. *A self-correction made the answer worse and looked like a success in the logs.* For "spanish
   music for a road trip", a `SHORT_LIST` violation triggered `relax_constraints`, which restored
   the full catalog and discarded the Spanish filter the user had explicitly asked for. Now
   relaxation only drops cues the system inferred and always keeps user-stated filters.

**The two honest partials from human evaluation:**
- `"korean music for the gym"` — correct language, but only 3 of 5 requested tracks exist in the
  catalog, and one (energy 0.46) is a weak gym fit. The shortfall is printed.
- `"classical for a workout"` — returns zero classical tracks. Energy wins over the stated genre,
  because genre is a soft +1.0 term while language is a hard filter. That inconsistency is
  documented in `model_card.md` rather than hidden. Confidence for that request is 0.38.

**Caveat to state out loud:** the 10 evaluation cases were written after watching the system run,
so a green 10/10 proves the system is consistent and constrained, not that its taste is good.
Judging taste requires listeners.

## Slide-by-slide spec

**Slide 1 — Title (20 s)**
Title "Resonance". Subtitle "A retrieval-grounded, self-checking music recommender". Third line:
"Extending Module 3: Music Recommender Simulation". Repo URL small at the bottom. Speaker notes:
one sentence on what the system does, one on what it extends.

**Slide 2 — The base project and its limit (45 s)**
Left: what VibeFinder did. Right: the `{"genre": "lofi", "mood": "chill", "energy": 0.35}` snippet
with a caption that this was the required input. One line: "It also had no idea if its answer was
good." Speaker notes must credit what the base project did well before naming the gap.

**Slide 3 — What I built (40 s)**
One line: "Same scorer. New everything around it." A 6-row list of the new modules with a
four-word purpose each. End with "no API key, runs offline".

**Slide 4 — Architecture (60 s)**
Reproduce the pipeline as a left-to-right flow with one loop:
`request → validate → retrieve → ground → recommend → critique → (revise, loop back) → explain → answer`,
with `data/knowledge/` and `data/knowledge_user/` feeding retrieve, `data/songs.csv` feeding
recommend, and traces flowing down to `logs/`. Highlight the critique-to-revise arrow in the
accent color, since that arrow is the difference between a pipeline and an agent. Note in the
speaker notes that the Mermaid source is committed at `diagrams/architecture.mmd`.

**Slide 5 — Live demo: retrieval doing real work (55 s)**
The `clean hip-hop for lifting` request. Show the "Grounded in", "Profile", "Confidence", and
"Stated by you" lines. Point out that the user never gave a number, and that the system labels
which preferences came from documents and which came from the listener's own words.

**Slide 6 — The agent catching itself (65 s)**
The 6-line trace block. Walk it: attempt 1 leaked an explicit track, the critic flagged
`EXPLICIT_LEAK`, the agent converted a soft penalty into a hard filter, attempt 2 passed. State
that attempt 1 was never shown to the user, and that traces are written to
`logs/traces/<run_id>.json` on every run.

**Slide 7 — Guardrails and honest failure (55 s)**
Three short blocks: the `NO_GROUNDING` refusal, the crisis-referral refusal (say only that a
crisis phrase returns a referral instead of a playlist, and that the check runs before any
retrieval), and the `korean music for the gym` shortfall warning. Theme line: "It refuses, and it
prints its warnings."

**Slide 8 — Evidence (60 s)**
Four numbers, large: 60/60 tests, 10/10 cases, mean confidence 0.71, and the retrieval-impact
row 0% → 80% for the studying request. Add the specialization line: score arithmetic in
explanations 100% → 0%. Immediately follow with the caveat that the cases were authored after
watching the system run.

**Slide 9 — What went wrong, and what I changed (70 s)**
Two items only: the inferred-vs-stated preference bug, and the self-correction that deleted the
user's Spanish filter. For each: one line for the symptom, one line for the structural fix. End
with the two honest partials on one line: "Two evaluation requests still fail honestly, and the
system says so."

**Slide 10 — What I learned (40 s)**
Three lines, no more:
- The agent loop worked on the first run. The knowledge corpus took four rounds of tuning.
- A confident self-correction is indistinguishable from a confident mistake in the logs.
- Traces were the highest-leverage thing I built.
Close on the repo URL.

## Output format

Return, in this order:
1. The 10 slides, each as a heading plus its bullet lines and any code block, ready to paste.
2. A separate speaker-notes section, one paragraph per slide, each prefixed with its target
   seconds, summing to 5:00-7:00.
3. A one-line total word count for the speaker notes so I can check the timing.
