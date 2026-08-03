"""
Command-line entry point for Resonance.

    python -m src.cli "something calm for studying, no lyrics"
    python -m src.cli "gym session, hype" --k 3 --trace
    python -m src.cli "..." --json
    python -m src.cli --show-sources
"""

import argparse
import json
import sys
from typing import List

from tabulate import tabulate

from src.agent import DEFAULT_CATALOG, DEFAULT_SOURCES, AgentResult, RecommenderAgent
from src.trace import get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Resonance - a retrieval-grounded, self-checking music recommender.",
    )
    parser.add_argument("query", nargs="?", help="what you want to listen to, in plain language")
    parser.add_argument("--k", type=int, default=5, help="number of songs to return (default 5)")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, help="path to the song CSV")
    parser.add_argument("--knowledge-dir", action="append", default=None,
                        help="knowledge directory (repeatable; defaults to both built-in sources)")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument("--trace", action="store_true", help="print the agent's reasoning trace")
    parser.add_argument("--no-save-trace", action="store_true", help="do not write logs/traces/<id>.json")
    parser.add_argument("--show-sources", action="store_true",
                        help="list the indexed knowledge sources and exit")
    parser.add_argument("--verbose", action="store_true", help="show INFO logs on stderr")
    return parser


def _render(result: AgentResult, show_trace: bool) -> str:
    lines: List[str] = []

    if not result.ok and not result.recommendations:
        lines.append("REFUSED [%s]" % result.refusal_code)
        lines.append(result.refusal)
        if show_trace and result.trace:
            lines.append("")
            lines.append(result.trace.render())
        return "\n".join(lines)

    profile = result.profile
    lines.append("Request: %s" % result.query)
    lines.append("Grounded in: %s" % ", ".join(
        "%s (%.2f)" % (doc_id, score) for doc_id, score in profile.evidence))
    lines.append("Profile: genre=%s mood=%s energy=%.2f language=%s avoid_explicit=%s strategy=%s" % (
        profile.prefs.get("genre") or "-",
        profile.prefs.get("mood") or "-",
        float(profile.prefs.get("energy", 0.5)),
        profile.prefs.get("language", "-"),
        profile.prefs.get("avoid_explicit"),
        profile.strategy,
    ))
    lines.append("Confidence: %.2f" % result.confidence)
    if profile.overrides:
        lines.append("Stated by you (overrode retrieval): %s" % ", ".join(profile.overrides))

    if result.revisions:
        lines.append("")
        lines.append("Self-corrections:")
        for revision in result.revisions:
            lines.append("  - %s" % revision)

    rows = [
        [i + 1, s["title"], s["artist"], s["genre"], "%.2f" % float(s["energy"]),
         "yes" if s["explicit"] else "no", "%.2f" % score]
        for i, (s, score, _) in enumerate(result.recommendations)
    ]
    lines.append("")
    lines.append(tabulate(
        rows,
        headers=["#", "Title", "Artist", "Genre", "Energy", "Explicit", "Score"],
        tablefmt="grid",
    ))

    lines.append("")
    lines.append("Why these:")
    for song, _, why in result.recommendations:
        lines.append("  %s - %s" % (song["title"], why))

    if result.violations:
        lines.append("")
        lines.append("WARNING - unresolved after %d revision(s):" % len(result.revisions))
        for violation in result.violations:
            lines.append("  [%s] %s" % (violation.code, violation.detail))

    if show_trace and result.trace:
        lines.append("")
        lines.append(result.trace.render())

    return "\n".join(lines)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    logger = get_logger()
    if not args.verbose:
        logger.handlers[0].setLevel("WARNING")  # stderr handler only; the file log stays at INFO

    knowledge_dirs = tuple(args.knowledge_dir) if args.knowledge_dir else DEFAULT_SOURCES

    try:
        agent = RecommenderAgent(catalog_path=args.catalog, knowledge_dirs=knowledge_dirs)
    except Exception as exc:  # startup failures should be a clean message, not a traceback
        print("Startup failed: %s" % exc, file=sys.stderr)
        return 2

    if args.show_sources:
        print("Indexed knowledge sources:")
        for source, count in sorted(agent.retriever.describe_sources().items()):
            print("  %-28s %d document(s)" % (source, count))
        for doc in agent.retriever.documents:
            print("  - %-26s %s [weight %.1f]" % (doc.doc_id, doc.title, doc.source_weight))
        return 0

    if args.query is None:
        print("No request given. Example:\n  python -m src.cli \"something calm for studying\"",
              file=sys.stderr)
        return 2

    result = agent.run(args.query, k=args.k)

    if not args.no_save_trace and result.trace:
        result.trace.save()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, default=str))
    else:
        print(_render(result, show_trace=args.trace))

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
