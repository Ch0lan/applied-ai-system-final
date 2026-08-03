"""
Grounding layer (the "A" in RAG): turn a free-text request plus the retrieved
documents into a concrete scoring profile for the Module 3 recommender.

This is where retrieval actually changes behavior. The retrieved documents supply the
genre / mood / energy / language / strategy cues that the recommender scores against;
without retrieval the system has no profile to score with at all.

Explicit statements in the user's own words always override retrieved cues, because a
document is a prior and the user's sentence is evidence.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.retriever import Document

# Cue keys merged from retrieved documents, in the order they are reported.
CUE_KEYS = ("genre", "mood", "energy", "likes_acoustic", "avoid_explicit", "language", "strategy")

LANGUAGE_PATTERNS = {
    "spanish": r"\bspanish|espanol|latin\b",
    "korean": r"\bkorean|k-?pop\b",
    "japanese": r"\bjapanese|j-?pop|city ?pop\b",
    "english": r"\benglish\b",
    "instrumental": r"\binstrumental|no lyrics|no words|without lyrics|no vocals|nothing with singing\b",
}

EXPLICIT_AVOID_PATTERN = r"\bno explicit|non-?explicit|clean\b|\bkid|kids|child|family[- ]friendly|work[- ]safe|sfw\b"
EXPLICIT_ALLOW_PATTERN = r"\bexplicit is fine|explicit ok|don'?t care about explicit\b"

HIGH_ENERGY_PATTERN = r"\bhigh energy|energetic|hype|pump|intense|loud|fast\b"
LOW_ENERGY_PATTERN = r"\blow energy|calm|quiet|slow|gentle|soft|mellow|sleepy\b"

# Known catalog values, used only to detect a directly named genre in the request.
KNOWN_GENRES = (
    "lofi", "ambient", "classical", "jazz", "rock", "indie rock", "indie pop", "pop",
    "k-pop", "latin pop", "city pop", "synthwave", "edm", "hip-hop", "metal", "country", "r&b",
)


@dataclass
class ProfileResult:
    """A scoring profile plus everything needed to explain where it came from."""
    prefs: Dict[str, object]
    strategy: str
    confidence: float
    evidence: List[Tuple[str, float]] = field(default_factory=list)   # (doc_id, retrieval score)
    provenance: Dict[str, str] = field(default_factory=dict)          # cue -> "doc:study-focus" | "user request"
    overrides: List[str] = field(default_factory=list)                # cues taken from the query text

    def as_dict(self) -> Dict[str, object]:
        return {
            "prefs": self.prefs,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 2),
            "evidence": [{"doc_id": d, "score": round(s, 3)} for d, s in self.evidence],
            "provenance": self.provenance,
            "overrides": self.overrides,
        }


def _parse_query_overrides(query: str) -> Dict[str, object]:
    """Extract preferences the user stated outright. These beat retrieved cues."""
    text = query.lower()
    overrides: Dict[str, object] = {}

    for language, pattern in LANGUAGE_PATTERNS.items():
        if re.search(pattern, text):
            overrides["language"] = language
            break

    if re.search(EXPLICIT_ALLOW_PATTERN, text):
        overrides["avoid_explicit"] = False
    elif re.search(EXPLICIT_AVOID_PATTERN, text):
        overrides["avoid_explicit"] = True

    # Longest match first so "indie rock" is not shadowed by "rock".
    for genre in sorted(KNOWN_GENRES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(genre) + r"\b", text):
            overrides["genre"] = genre
            break

    if re.search(HIGH_ENERGY_PATTERN, text):
        overrides["energy"] = 0.9
    elif re.search(LOW_ENERGY_PATTERN, text):
        overrides["energy"] = 0.25

    return overrides


def _merge_cues(retrieved: List[Tuple[Document, float]]) -> Tuple[Dict[str, object], Dict[str, str]]:
    """
    Merge cues across retrieved documents.

    Categorical cues (genre, mood, language, strategy) use score-weighted voting.
    Numeric energy uses a score-weighted mean. Booleans use a score-weighted vote where
    True wins ties, so a safety-relevant cue like avoid_explicit is never lost to rounding.
    """
    cues: Dict[str, object] = {}
    provenance: Dict[str, str] = {}
    if not retrieved:
        return cues, provenance

    for key in CUE_KEYS:
        contributors = [(doc, score) for doc, score in retrieved if key in doc.cues]
        if not contributors:
            continue

        if key == "energy":
            total = sum(score for _, score in contributors)
            cues[key] = round(
                sum(float(doc.cues[key]) * score for doc, score in contributors) / total, 3
            )
            provenance[key] = "+".join(doc.doc_id for doc, _ in contributors)
            continue

        votes: Dict[object, float] = {}
        winner_doc: Dict[object, str] = {}
        for doc, score in contributors:
            value = doc.cues[key]
            votes[value] = votes.get(value, 0.0) + score
            winner_doc.setdefault(value, doc.doc_id)

        if key in ("likes_acoustic", "avoid_explicit") and True in votes:
            # Ties go to the more conservative option.
            best = True if votes.get(True, 0.0) >= votes.get(False, 0.0) else False
        else:
            best = max(votes.items(), key=lambda kv: kv[1])[0]

        cues[key] = best
        provenance[key] = winner_doc[best]

    return cues, provenance


def _confidence(retrieved: List[Tuple[Document, float]], overrides: Dict[str, object]) -> float:
    """
    Confidence in the derived profile, in [0, 1].

    Three additive signals:
      - retrieval strength: how well the best document matched (saturating)
      - agreement: whether the top documents point at the same mood
      - grounding: whether the user stated preferences outright
    """
    if not retrieved:
        return 0.0

    top_score = retrieved[0][1]
    strength = min(top_score / 8.0, 1.0) * 0.6

    moods = [doc.cues.get("mood") for doc, _ in retrieved if "mood" in doc.cues]
    if len(moods) > 1:
        agreement = (moods.count(moods[0]) / len(moods)) * 0.25
    else:
        agreement = 0.25 if moods else 0.0

    grounding = min(len(overrides), 3) / 3 * 0.15

    return round(min(strength + agreement + grounding, 1.0), 3)


def build_profile(query: str, retrieved: List[Tuple[Document, float]]) -> ProfileResult:
    """Build the scoring profile for `query` from the retrieved documents."""
    cues, provenance = _merge_cues(retrieved)
    overrides = _parse_query_overrides(query)

    for key, value in overrides.items():
        cues[key] = value
        provenance[key] = "user request"

    prefs: Dict[str, object] = {
        "genre": cues.get("genre", ""),
        "mood": cues.get("mood", ""),
        "energy": float(cues.get("energy", 0.5)),
        "likes_acoustic": cues.get("likes_acoustic"),
        "avoid_explicit": bool(cues.get("avoid_explicit", False)),
    }
    if "language" in cues:
        prefs["language"] = cues["language"]

    return ProfileResult(
        prefs=prefs,
        strategy=str(cues.get("strategy", "balanced")),
        confidence=_confidence(retrieved, overrides),
        evidence=[(doc.doc_id, score) for doc, score in retrieved],
        provenance={k: provenance[k] for k in provenance},
        overrides=sorted(overrides.keys()),
    )
