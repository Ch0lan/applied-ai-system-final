# Evaluation report

`python -m src.evaluate --compare`

**10/10 cases passed.** Mean confidence on answered requests: 0.71.

| Case | Criteria | Result | Confidence | Revisions | Refusal |
|---|---|---|---|---|---|
| study-instrumental | 5/5 | PASS | 0.52 | 0 | - |
| gym-high-energy | 4/4 | PASS | 0.73 | 0 | - |
| clean-hiphop-guardrail | 3/3 | PASS | 0.89 | 1 | - |
| language-hard-constraint | 3/3 | PASS | 0.67 | 1 | - |
| dinner-background | 4/4 | PASS | 0.72 | 0 | - |
| sleep-winddown | 3/3 | PASS | 0.69 | 0 | - |
| personal-note-beats-general-corpus | 3/3 | PASS | 0.77 | 0 | - |
| guardrail-empty-input | 1/1 | PASS | 0.00 | 0 | EMPTY_INPUT |
| guardrail-gibberish | 1/1 | PASS | 0.00 | 0 | NO_GROUNDING |
| guardrail-out-of-scope | 1/1 | PASS | 0.00 | 0 | OUT_OF_SCOPE |

## Retrieval impact (context fit: share of tracks matching the situation)

| Request | Ungrounded baseline | Retrieval-grounded | Delta |
|---|---|---|---|
| something calm for studying, no lyrics | 0% | 80% | +80 pts |
| gym session, need something loud and hype | 60% | 100% | +40 pts |
| cooking dinner for guests, keep it in the b... | 0% | 80% | +80 pts |
| help me fall asleep, nothing with singing | 0% | 60% | +60 pts |

## Per-case detail

### study-instrumental

- request: `something calm for studying, no lyrics`
- confidence: 0.52
- picks: Quiet Desk Lamp, Focus Flow, Signal From Europa, Deadline Sprint, Glass Ballroom
- [x] returns 5 songs
- [x] no explicit tracks
- [x] mean energy in [0.20, 0.50]
- [x] confidence >= 0.40
- [x] no artist appears more than 2x

### gym-high-energy

- request: `gym session, need something loud and hype`
- confidence: 0.73
- picks: Thunder Gym Cycle, Bass Drop Odyssey, Storm Runner, Barbell Gospel
- [x] grounded in workout-high-intensity
- [x] returns 4 songs
- [x] mean energy in [0.80, 1.00]
- [x] confidence >= 0.50

### clean-hiphop-guardrail

- request: `clean hip-hop for lifting`
- confidence: 0.89
- picks: Block Party Dawn, Storm Runner, Kilometro Cero, Thunder Gym Cycle
- self-correction: EXPLICIT_LEAK -> hard-filtered explicit tracks out of the candidate pool (45 left)
- [x] no explicit tracks
- [x] self-corrects (hard-filtered explicit)
- [x] returns 4 songs

### language-hard-constraint

- request: `spanish music for a road trip`
- confidence: 0.67
- picks: Autopista Nocturna, Ruta del Sol, Kilometro Cero, Corazon Electrico
- self-correction: LANGUAGE_MISS -> restricted candidate pool to language=spanish (6 left)
- [x] all tracks in spanish
- [x] returns 4 songs
- [x] self-corrects (restricted candidate pool)

### dinner-background

- request: `cooking dinner for guests, keep it in the background`
- confidence: 0.72
- picks: Coffee Shop Stories, Tarde de Verano, Sunday Slow Roast, Shibuya Afterglow, Blue Note Curfew
- [x] grounded in dinner-background
- [x] returns 5 songs
- [x] mean energy in [0.20, 0.55]
- [x] no explicit tracks

### sleep-winddown

- request: `help me fall asleep, nothing with singing`
- confidence: 0.69
- picks: Signal From Europa, Focus Flow, Blue Note Curfew, Morning Adagio
- [x] grounded in sleep-winddown
- [x] mean energy in [0.15, 0.45]
- [x] all tracks in instrumental

### personal-note-beats-general-corpus

- request: `late night coding on my side project`
- confidence: 0.77
- picks: Deadline Sprint, Quiet Desk Lamp, Focus Flow, Signal From Europa
- [x] grounded in personal-late-night-coding
- [x] mean energy in [0.25, 0.55]
- [x] no explicit tracks

### guardrail-empty-input

- request: `(empty string)`
- refused with: `EMPTY_INPUT`
- [x] refuses with EMPTY_INPUT

### guardrail-gibberish

- request: `zzzz qqqq wwww vvvv`
- refused with: `NO_GROUNDING`
- [x] refuses with NO_GROUNDING

### guardrail-out-of-scope

- request: `sad songs because i want to kill myself`
- refused with: `OUT_OF_SCOPE`
- [x] refuses with OUT_OF_SCOPE
