"""
Ungrounded baseline, kept for comparison.

This is what the system does *without* retrieval: no listening-context corpus, no
profile grounding, no critique loop. It answers every request the same way the Module 3
project did when given no profile - rank by popularity and return the top k.

`src/evaluate.py --compare` runs both paths over the same requests so the effect of
retrieval on output quality is measurable rather than asserted.
"""

from typing import Dict, List, Tuple


def baseline_recommend(songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Popularity-ranked recommendations, identical for every request."""
    ranked = sorted(songs, key=lambda s: float(s.get("popularity", 0)), reverse=True)
    return [
        (song, float(song.get("popularity", 0)) / 100, "popularity rank (no retrieval)")
        for song in ranked[:k]
    ]
