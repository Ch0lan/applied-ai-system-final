# Custom knowledge source

This directory is the **second retrieval source**. It is indexed alongside `data/knowledge/`
but each document may declare a `source_weight` in its front matter, which multiplies its BM25
score. Personal notes are given a weight above 1.0 so that, when a personal note and a general
document both match a query, the personal note wins the profile-cue merge.

Drop any number of `.md` files here using the same front-matter schema as `data/knowledge/`:

```
---
id: unique-slug
title: Human readable title
tags: comma, separated, trigger, words
genre: lofi
mood: focused
energy: 0.42
likes_acoustic: false
avoid_explicit: true
language: instrumental
strategy: mood-first
source_weight: 1.6
---

Free prose. The body text is indexed too, not just the tags.
```

Every front-matter field except `id`, `title`, and `tags` is optional. Run
`python -m src.cli --show-sources` to confirm a new file was picked up.
