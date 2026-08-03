"""
The agent: a plan -> act -> check -> revise loop around the Module 3 recommender.

    plan       decide which tools this request needs
    retrieve   BM25 over the listening-context corpus            (tool: KnowledgeRetriever)
    ground     merge retrieved cues + stated preferences         (tool: build_profile)
    recommend  score and rank the catalog                        (tool: recommend_songs)
    critique   run output guardrails against the result          (tool: critique_recommendations)
    revise     apply a concrete fix and re-run, up to MAX_REVISIONS

The loop is what makes this an agent rather than a pipeline: the critique step can send
control back to `recommend` with different constraints, and the final answer is whichever
attempt survived critique (or the best attempt, clearly labelled, if none did).
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.guardrails import ValidationResult, Violation, critique_recommendations, validate_query
from src.profile_builder import ProfileResult, build_profile
from src.recommender import load_songs, recommend_songs
from src.retriever import KnowledgeRetriever, RetrievalError
from src.trace import Trace, get_logger

DEFAULT_CATALOG = os.path.join("data", "songs.csv")
DEFAULT_SOURCES = (os.path.join("data", "knowledge"), os.path.join("data", "knowledge_user"))

MAX_REVISIONS = 2
RETRIEVE_K = 3
BROADENED_RETRIEVE_K = 6
DEFAULT_ARTIST_CAP = 2


@dataclass
class AgentResult:
    """Everything one run produced, including the attempts that were rejected."""
    query: str
    ok: bool
    recommendations: List[Tuple[Dict, float, str]] = field(default_factory=list)
    profile: Optional[ProfileResult] = None
    violations: List[Violation] = field(default_factory=list)
    revisions: List[str] = field(default_factory=list)
    trace: Optional[Trace] = None
    refusal: str = ""
    refusal_code: str = ""

    @property
    def confidence(self) -> float:
        return self.profile.confidence if self.profile else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "ok": self.ok,
            "refusal_code": self.refusal_code,
            "refusal": self.refusal,
            "confidence": round(self.confidence, 2),
            "profile": self.profile.as_dict() if self.profile else None,
            "revisions": self.revisions,
            "unresolved_violations": [v.as_dict() for v in self.violations],
            "recommendations": [
                {
                    "title": s["title"],
                    "artist": s["artist"],
                    "genre": s["genre"],
                    "language": s["language"],
                    "explicit": bool(s["explicit"]),
                    "energy": float(s["energy"]),
                    "score": round(score, 2),
                    "why": why,
                }
                for s, score, why in self.recommendations
            ],
            "trace": self.trace.as_dict() if self.trace else None,
        }


class RecommenderAgent:
    """Stateless across runs; each `run()` owns its own trace and constraint state."""

    def __init__(
        self,
        catalog_path: str = DEFAULT_CATALOG,
        knowledge_dirs: Tuple[str, ...] = DEFAULT_SOURCES,
        quiet: bool = True,
    ):
        self.log = get_logger()
        self.songs = _load_catalog(catalog_path, quiet=quiet)
        if not self.songs:
            raise ValueError("catalog %s is empty" % catalog_path)
        self.retriever = KnowledgeRetriever.from_directories(knowledge_dirs)
        self.log.info(
            "agent ready: %d songs, %d knowledge docs from %s",
            len(self.songs), len(self.retriever.documents),
            ", ".join(sorted(self.retriever.describe_sources())),
        )

    # -- tools ---------------------------------------------------------------

    def _tool_retrieve(self, query: str, k: int):
        return self.retriever.retrieve(query, k=k)

    def _tool_rank(
        self,
        prefs: Dict[str, object],
        strategy: str,
        catalog: List[Dict],
        k: int,
        artist_cap: int,
    ) -> List[Tuple[Dict, float, str]]:
        """Rank the catalog, then apply the hard per-artist cap the ranker only softly penalizes."""
        if not catalog:
            return []
        ranked = recommend_songs(prefs, catalog, k=len(catalog), mode=strategy)
        capped: List[Tuple[Dict, float, str]] = []
        counts: Dict[str, int] = {}
        for song, score, why in ranked:
            artist = song["artist"]
            if counts.get(artist, 0) >= artist_cap:
                continue
            counts[artist] = counts.get(artist, 0) + 1
            capped.append((song, score, why))
            if len(capped) == k:
                break
        return capped

    # -- revision actions ----------------------------------------------------

    def _apply_fix(
        self,
        fix: str,
        state: Dict[str, Any],
        query: str,
    ) -> Optional[str]:
        """
        Mutate the run state according to a guardrail's suggested fix.
        Returns a human-readable description, or None if the fix cannot help further.
        """
        if fix == "hard_filter_explicit":
            if state["explicit_filtered"]:
                return None
            state["catalog"] = [s for s in state["catalog"] if not s.get("explicit")]
            state["explicit_filtered"] = True
            return "hard-filtered explicit tracks out of the candidate pool (%d left)" % len(state["catalog"])

        if fix == "hard_filter_language":
            language = state["profile"].prefs.get("language")
            if not language or state["language_filtered"]:
                return None
            filtered = [
                s for s in state["catalog"]
                if str(s.get("language", "")).lower() == str(language).lower()
            ]
            if not filtered:
                return None
            state["catalog"] = filtered
            state["language_filtered"] = True
            return "restricted candidate pool to language=%s (%d left)" % (language, len(filtered))

        if fix == "enforce_diversity":
            if state["artist_cap"] <= 1:
                return None
            state["artist_cap"] = 1
            return "tightened per-artist cap to 1 track"

        if fix == "switch_to_energy_strategy":
            if state["strategy"] == "energy-focused":
                return None
            state["strategy"] = "energy-focused"
            return "switched ranking strategy to energy-focused to close the energy gap"

        if fix == "broaden_retrieval":
            if state["retrieve_k"] >= BROADENED_RETRIEVE_K:
                return None
            state["retrieve_k"] = BROADENED_RETRIEVE_K
            retrieved = self._tool_retrieve(query, k=state["retrieve_k"])
            if not retrieved:
                return None
            profile = build_profile(query, retrieved)
            state["profile"] = profile
            state["strategy"] = profile.strategy
            return "re-retrieved with k=%d, confidence %.2f -> %.2f" % (
                BROADENED_RETRIEVE_K, state["last_confidence"], profile.confidence)

        if fix == "relax_constraints":
            if state["relaxed"]:
                return None
            state["relaxed"] = True
            # Rebuild the pool from scratch, but keep every filter the listener asked for
            # by name. Relaxing is for cues the system inferred, never for stated ones.
            profile = state["profile"]
            stated = set(profile.overrides)
            catalog = list(state["full_catalog"])
            kept = []
            if state["explicit_filtered"] and profile.prefs.get("avoid_explicit"):
                catalog = [s for s in catalog if not s.get("explicit")]
                kept.append("explicit filter")
            else:
                state["explicit_filtered"] = False
            if state["language_filtered"] and "language" in stated:
                language = str(profile.prefs.get("language", "")).lower()
                catalog = [s for s in catalog if str(s.get("language", "")).lower() == language]
                kept.append("language=%s" % language)
            else:
                state["language_filtered"] = False
            state["catalog"] = catalog
            profile.prefs["genre"] = ""
            note = "relaxed the genre constraint (%d candidates)" % len(catalog)
            if kept:
                note += "; kept " + " and ".join(kept)
            return note

        return None

    # -- main loop -----------------------------------------------------------

    def run(self, query: str, k: int = 5, artist_cap: int = DEFAULT_ARTIST_CAP) -> AgentResult:
        trace = Trace(query=str(query))

        validation: ValidationResult = validate_query(query)
        trace.add("validate_input", **validation.as_dict())
        if not validation.ok:
            self.log.warning("rejected request (%s): %s", validation.code, validation.reason)
            return AgentResult(
                query=str(query), ok=False, trace=trace,
                refusal=validation.message, refusal_code=validation.code,
            )

        query = str(query).strip()
        trace.add("plan", tools=["retrieve", "ground", "rank", "critique"], max_revisions=MAX_REVISIONS)

        try:
            retrieved = self._tool_retrieve(query, k=RETRIEVE_K)
        except RetrievalError as exc:
            trace.add("retrieve_failed", error=str(exc))
            return AgentResult(query=query, ok=False, trace=trace,
                               refusal="Knowledge base unavailable: %s" % exc,
                               refusal_code="RETRIEVAL_ERROR")

        trace.add(
            "retrieve",
            k=RETRIEVE_K,
            hits=[("%s(%.2f)" % (d.doc_id, s)) for d, s in retrieved],
        )

        if not retrieved:
            trace.add("no_grounding")
            self.log.warning("no knowledge document matched %r", query)
            return AgentResult(
                query=query, ok=False, trace=trace, refusal_code="NO_GROUNDING",
                refusal=("Nothing in the listening-context knowledge base matched that request, "
                         "so there is no grounded profile to recommend from. Try naming the "
                         "situation (studying, workout, party, driving, dinner, sleep) or a genre."),
            )

        profile = build_profile(query, retrieved)
        trace.add(
            "ground",
            prefs=profile.prefs,
            strategy=profile.strategy,
            confidence=profile.confidence,
            overrides=profile.overrides,
            provenance=profile.provenance,
        )

        state: Dict[str, Any] = {
            "profile": profile,
            "strategy": profile.strategy,
            "catalog": list(self.songs),
            "full_catalog": list(self.songs),
            "artist_cap": artist_cap,
            "retrieve_k": RETRIEVE_K,
            "explicit_filtered": False,
            "language_filtered": False,
            "relaxed": False,
            "last_confidence": profile.confidence,
        }

        revisions: List[str] = []
        best: List[Tuple[Dict, float, str]] = []
        violations: List[Violation] = []

        for attempt in range(MAX_REVISIONS + 1):
            profile = state["profile"]
            state["last_confidence"] = profile.confidence
            recommendations = self._tool_rank(
                profile.prefs, state["strategy"], state["catalog"], k, state["artist_cap"]
            )
            trace.add(
                "recommend",
                attempt=attempt + 1,
                strategy=state["strategy"],
                pool=len(state["catalog"]),
                picks=[s["title"] for s, _, _ in recommendations],
            )

            violations = critique_recommendations(
                recommendations, profile.prefs, profile.confidence, k,
                user_stated=profile.overrides,
            )
            trace.add(
                "critique",
                attempt=attempt + 1,
                passed=not violations,
                violations=[v.code for v in violations],
            )

            if recommendations:
                best = recommendations

            if not violations:
                trace.add("finalize", status="passed_critique", revisions=len(revisions))
                return AgentResult(query=query, ok=True, recommendations=recommendations,
                                   profile=profile, revisions=revisions, trace=trace)

            if attempt == MAX_REVISIONS:
                break

            applied = []
            for violation in violations:
                description = self._apply_fix(violation.fix, state, query)
                if description:
                    applied.append("%s -> %s" % (violation.code, description))

            if not applied:
                trace.add("revise", attempt=attempt + 1, applied=[], note="no further fixes available")
                break

            revisions.extend(applied)
            trace.add("revise", attempt=attempt + 1, applied=applied)

        trace.add(
            "finalize",
            status="returned_with_warnings",
            revisions=len(revisions),
            unresolved=[v.code for v in violations],
        )
        self.log.warning(
            "run %s finished with %d unresolved violation(s): %s",
            trace.run_id, len(violations), ", ".join(v.code for v in violations),
        )
        return AgentResult(
            query=query,
            ok=bool(best) and all(v.code != "NO_RESULTS" for v in violations),
            recommendations=best,
            profile=state["profile"],
            violations=violations,
            revisions=revisions,
            trace=trace,
        )


def _load_catalog(path: str, quiet: bool) -> List[Dict]:
    """Load the CSV catalog. `load_songs` prints progress, which we suppress by default."""
    if not os.path.exists(path):
        raise FileNotFoundError("catalog not found: %s" % path)
    if not quiet:
        return load_songs(path)

    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return load_songs(path)
