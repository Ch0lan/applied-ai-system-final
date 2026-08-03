# Explanation style specification (few-shot)

The scorer produces arithmetic. This file specifies the **voice** that arithmetic is rendered in,
as a small set of few-shot exemplars plus a phrase table. `src/explainer.py` reads this file at
runtime — changing the style means editing this document, not the code.

## Style constraints

- second person, addressed to the listener
- no numbers, no score arithmetic, no internal field names
- at most two clauses, joined by a comma or a dash
- at most 140 characters
- lead with the strongest reason; safety-relevant clauses (explicit filtering) go last
- never claim a match the score did not actually contain

## Phrase table

| component | phrase |
|---|---|
| genre match | the {genre} you asked for |
| mood match | it lands in a {mood} mood |
| energy similarity | sits right in the energy range you wanted |
| acoustic match | acoustic, the way you like it |
| too acoustic for preference | a little more acoustic than you usually go |
| mood tag match | the exact {mood_tag} feel you described |
| language match | sung in {language} |
| popularity fit | about as well-known as you wanted |
| explicit content avoided | flagged explicit, so it is ranked down |
| artist diversity penalty | ranked down so one artist does not take over |
| no strong matches | nothing here matches strongly, it is the closest the catalog gets |

## Few-shot exemplars

Each exemplar is `raw scorer output` followed by the styled rendering it should produce.

**Exemplar 1**

```
raw:    genre match (+1.0), mood match (+2.5), energy similarity (+0.92), language match (+0.5)
styled: The lofi you asked for, and it lands in a focused mood - sung in instrumental.
```

**Exemplar 2**

```
raw:    energy similarity (+2.97), mood match (+0.5)
styled: Sits right in the energy range you wanted, and it lands in an intense mood.
```

**Exemplar 3**

```
raw:    genre match (+1.0), energy similarity (+2.64), artist diversity penalty (-1.0)
styled: The hip-hop you asked for, sits right in the energy range you wanted - ranked down so one artist does not take over.
```

**Exemplar 4**

```
raw:    energy similarity (+0.99), too acoustic for preference (-0.5)
styled: Sits right in the energy range you wanted - a little more acoustic than you usually go.
```
