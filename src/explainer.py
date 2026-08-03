"""
Specialized explanation layer.

The Module 3 scorer emits arithmetic: `genre match (+1.0), energy similarity (+0.92)`. That is
honest but reads like a debugger. This module renders the same components in a constrained
listener-facing voice defined by few-shot exemplars in `data/style/explanation_style.md`.

There is no generative model here, and this is not a fine-tune: the specialization is a
style contract (phrase table + constraints + worked exemplars) held in a data file and applied
deterministically, so the same input always produces the same sentence and the style can be
changed without touching code. `--plain` on the CLI returns the raw baseline strings, and
`python -m src.evaluate --style` measures the difference between the two.
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

STYLE_PATH = os.path.join("data", "style", "explanation_style.md")

MAX_CHARS = 140
MAX_CLAUSES = 2

# Components whose clause must come last: they qualify the recommendation rather than support it.
TRAILING_COMPONENTS = (
    "explicit content avoided",
    "artist diversity penalty",
    "too acoustic for preference",
)

# Strongest-first ordering for the supporting clauses.
COMPONENT_PRIORITY = (
    "genre match",
    "mood tag match",
    "mood match",
    "energy similarity",
    "acoustic match",
    "language match",
    "popularity fit",
)

_COMPONENT_RE = re.compile(r"^([a-z ]+?)\s*\([-+]", re.IGNORECASE)


class StyleError(Exception):
    """Raised when the style specification cannot be loaded."""


@dataclass
class ExplanationStyle:
    """The style contract: phrase table plus the exemplars that define the voice."""
    phrases: Dict[str, str]
    exemplars: List[Tuple[str, str]]
    max_chars: int = MAX_CHARS

    @classmethod
    def load(cls, path: str = STYLE_PATH) -> "ExplanationStyle":
        if not os.path.exists(path):
            raise StyleError("style specification not found: %s" % path)
        with open(path, encoding="utf-8") as f:
            text = f.read()

        phrases: Dict[str, str] = {}
        for line in text.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 2 or cells[0] in ("component", "---") or set(cells[0]) <= {"-"}:
                continue
            phrases[cells[0].lower()] = cells[1]

        exemplars = [
            (raw.strip(), styled.strip())
            for raw, styled in re.findall(r"raw:\s*(.+)\n\s*styled:\s*(.+)", text)
        ]

        if not phrases:
            raise StyleError("style specification has no phrase table: %s" % path)
        return cls(phrases=phrases, exemplars=exemplars)


def _component_name(fragment: str) -> Optional[str]:
    match = _COMPONENT_RE.match(fragment.strip())
    return match.group(1).strip().lower() if match else None


def _fill(phrase: str, song: Dict) -> str:
    """Substitute {genre}, {mood}, {language}, {mood_tag} from the song row."""
    def replace(match):
        key = match.group(1)
        return str(song.get(key, "")).strip() or key
    filled = re.sub(r"\{(\w+)\}", replace, phrase)
    # Substituted values change which article is correct ("a intense mood" -> "an intense mood").
    return re.sub(r"\ba (?=[aeiou])", "an ", filled)


class Explainer:
    """Renders raw scorer reason strings in the specified voice."""

    def __init__(self, style: Optional[ExplanationStyle] = None):
        self.style = style or ExplanationStyle.load()

    def render(self, song: Dict, raw_reasons: str) -> str:
        """Turn `raw_reasons` into one constrained, listener-facing sentence."""
        if not raw_reasons:
            return self._finish([self.style.phrases.get("no strong matches", "no strong matches")])

        names = [n for n in (_component_name(f) for f in raw_reasons.split(", ")) if n]
        if not names:
            return self._finish([self.style.phrases.get("no strong matches", "no strong matches")])

        leading = [n for n in names if n not in TRAILING_COMPONENTS]
        trailing = [n for n in names if n in TRAILING_COMPONENTS]

        leading.sort(key=lambda n: COMPONENT_PRIORITY.index(n) if n in COMPONENT_PRIORITY else 99)
        clauses = [_fill(self.style.phrases[n], song) for n in leading[:MAX_CLAUSES]
                   if n in self.style.phrases]

        if not clauses and trailing:
            clauses = [_fill(self.style.phrases[trailing[0]], song)]
            trailing = trailing[1:]

        sentence = ", and ".join(clauses) if len(clauses) > 1 else (clauses[0] if clauses else "")

        if trailing:
            qualifier = _fill(self.style.phrases.get(trailing[0], trailing[0]), song)
            sentence = "%s - %s" % (sentence, qualifier) if sentence else qualifier

        return self._finish([sentence])

    def _finish(self, parts: List[str]) -> str:
        sentence = " ".join(p for p in parts if p).strip()
        if not sentence:
            return ""
        sentence = sentence[0].upper() + sentence[1:]
        if len(sentence) > self.style.max_chars:
            sentence = sentence[: self.style.max_chars - 1].rstrip(" ,-") + "…"
        if not sentence.endswith((".", "…")):
            sentence += "."
        return sentence


def style_metrics(explanations: List[str]) -> Dict[str, float]:
    """Measurable properties of a set of explanation strings, for baseline-vs-styled comparison."""
    if not explanations:
        return {"count": 0, "mean_chars": 0.0, "digit_share": 0.0, "second_person_share": 0.0}
    digits = sum(1 for e in explanations if any(ch.isdigit() for ch in e))
    second_person = sum(1 for e in explanations if re.search(r"\byou\b|\byour\b", e, re.IGNORECASE))
    return {
        "count": len(explanations),
        "mean_chars": sum(len(e) for e in explanations) / len(explanations),
        "digit_share": digits / len(explanations),
        "second_person_share": second_person / len(explanations),
    }
