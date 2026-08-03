"""
Guardrails: input validation before the agent runs, and output critique after it runs.

Input validation rejects requests the system cannot serve honestly.
Output critique inspects the actual recommendation list and reports violations, which
is what lets the agent revise itself instead of shipping a bad answer.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

MIN_QUERY_CHARS = 3
MAX_QUERY_CHARS = 400
MIN_ALPHA_RATIO = 0.5
MIN_CONFIDENCE = 0.30
MAX_PER_ARTIST = 2
ENERGY_TOLERANCE = 0.25

# The corpus covers ordinary mood-congruent listening, not crisis support. Requests in
# this space get a referral instead of a playlist.
CRISIS_PATTERN = re.compile(
    r"\b(kill myself|suicide|suicidal|end my life|self ?harm|hurt myself|want to die)\b",
    re.IGNORECASE,
)

CRISIS_MESSAGE = (
    "This system only picks music and is not a source of mental-health support. "
    "If you are in crisis, please contact a local emergency number or, in the US, "
    "call or text 988 (Suicide & Crisis Lifeline)."
)


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""
    code: str = ""
    message: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {"ok": self.ok, "code": self.code, "reason": self.reason}


def validate_query(query: Optional[str]) -> ValidationResult:
    """Reject empty, oversized, non-linguistic, or out-of-scope requests."""
    if query is None or not str(query).strip():
        return ValidationResult(False, "empty request", "EMPTY_INPUT",
                                "Tell me what you want to listen to, e.g. 'something calm for studying'.")

    text = str(query).strip()

    if len(text) < MIN_QUERY_CHARS:
        return ValidationResult(False, "request too short to interpret", "TOO_SHORT",
                                "That is too short to work with - a few words about the situation is enough.")

    if len(text) > MAX_QUERY_CHARS:
        return ValidationResult(False, "request exceeds %d characters" % MAX_QUERY_CHARS, "TOO_LONG",
                                "That request is very long. Try one or two sentences describing the situation.")

    alpha = sum(ch.isalpha() or ch.isspace() for ch in text)
    if alpha / len(text) < MIN_ALPHA_RATIO:
        return ValidationResult(False, "request is mostly non-alphabetic", "NOT_LANGUAGE",
                                "I could not read that as a sentence. Try describing the moment in words.")

    if CRISIS_PATTERN.search(text):
        return ValidationResult(False, "request matches crisis-referral pattern", "OUT_OF_SCOPE",
                                CRISIS_MESSAGE)

    return ValidationResult(True)


@dataclass
class Violation:
    """One failed output check. `fix` names the revision the agent should attempt."""
    code: str
    detail: str
    fix: str

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "detail": self.detail, "fix": self.fix}


def critique_recommendations(
    recommendations: List[Tuple[Dict, float, str]],
    prefs: Dict[str, object],
    confidence: float,
    k: int,
    user_stated: Optional[List[str]] = None,
) -> List[Violation]:
    """
    Inspect a finished recommendation list against the profile that produced it.

    `user_stated` lists the preferences the listener asked for in their own words. Only
    those are enforced as hard constraints; a preference merely inferred from a retrieved
    document stays a soft scoring signal, so a document's default cannot silently
    override what the listener actually wanted.

    Returns an empty list when the output is acceptable. Each violation carries a `fix`
    code that `agent.py` maps to a concrete revision action.
    """
    violations: List[Violation] = []
    stated = set(user_stated or ())

    if not recommendations:
        violations.append(Violation(
            "NO_RESULTS", "recommender returned no songs", "relax_constraints"))
        return violations

    if len(recommendations) < k:
        violations.append(Violation(
            "SHORT_LIST",
            "asked for %d songs, got %d" % (k, len(recommendations)),
            "relax_constraints",
        ))

    if prefs.get("avoid_explicit"):
        leaked = [s["title"] for s, _, _ in recommendations if s.get("explicit")]
        if leaked:
            violations.append(Violation(
                "EXPLICIT_LEAK",
                "explicit tracks present despite avoid_explicit: %s" % ", ".join(leaked),
                "hard_filter_explicit",
            ))

    wanted_language = prefs.get("language") if "language" in stated else None
    if wanted_language:
        wrong = [
            s["title"] for s, _, _ in recommendations
            if str(s.get("language", "")).lower() != str(wanted_language).lower()
        ]
        # A language request is a near-filter, so tolerate at most one off-language track.
        if len(wrong) > 1:
            violations.append(Violation(
                "LANGUAGE_MISS",
                "%d of %d tracks are not %s" % (len(wrong), len(recommendations), wanted_language),
                "hard_filter_language",
            ))

    artist_counts: Dict[str, int] = {}
    for song, _, _ in recommendations:
        artist_counts[song["artist"]] = artist_counts.get(song["artist"], 0) + 1
    crowding = [a for a, c in artist_counts.items() if c > MAX_PER_ARTIST]
    if crowding:
        violations.append(Violation(
            "ARTIST_CROWDING",
            "artist over-represented (>%d tracks): %s" % (MAX_PER_ARTIST, ", ".join(crowding)),
            "enforce_diversity",
        ))

    target_energy = float(prefs.get("energy", 0.5))
    mean_energy = sum(float(s["energy"]) for s, _, _ in recommendations) / len(recommendations)
    if abs(mean_energy - target_energy) > ENERGY_TOLERANCE:
        violations.append(Violation(
            "ENERGY_DRIFT",
            "mean energy %.2f vs target %.2f" % (mean_energy, target_energy),
            "switch_to_energy_strategy",
        ))

    if confidence < MIN_CONFIDENCE:
        violations.append(Violation(
            "LOW_CONFIDENCE",
            "profile confidence %.2f below %.2f" % (confidence, MIN_CONFIDENCE),
            "broaden_retrieval",
        ))

    return violations
