"""
Structured logging and reasoning traces.

Every agent run produces a Trace: an ordered list of steps with their inputs and
outputs. Traces are written to logs/traces/<run_id>.json so the agent's intermediate
reasoning is inspectable after the fact rather than only printed to a terminal.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LOG_DIR = "logs"
TRACE_DIR = os.path.join(LOG_DIR, "traces")
RUN_LOG = os.path.join(LOG_DIR, "run.log")

_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Module-wide logger writing to both stderr and logs/run.log."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("resonance")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = logging.FileHandler(RUN_LOG, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:  # read-only filesystem: keep running with stderr only
        logger.warning("file logging disabled (%s)", exc)

    _logger = logger
    return logger


@dataclass
class TraceStep:
    step: int
    name: str
    detail: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "name": self.name,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "detail": self.detail,
        }


@dataclass
class Trace:
    """An ordered record of one agent run."""
    query: str
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    steps: List[TraceStep] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def add(self, name: str, **detail: Any) -> TraceStep:
        step = TraceStep(
            step=len(self.steps) + 1,
            name=name,
            detail=detail,
            elapsed_ms=(time.time() - self.started_at) * 1000,
        )
        self.steps.append(step)
        get_logger().info("[%s] step %d %s", self.run_id, step.step, name)
        return step

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "started_at": self.started_at,
            "steps": [s.as_dict() for s in self.steps],
        }

    def render(self) -> str:
        """Human-readable trace, used by --trace and by ai_interactions.md."""
        lines = ["Trace %s | query: %r" % (self.run_id, self.query)]
        for step in self.steps:
            lines.append("  %d. %-22s %s" % (step.step, step.name, _compact(step.detail)))
        return "\n".join(lines)

    def save(self, directory: str = TRACE_DIR) -> Optional[str]:
        """Persist the trace as JSON. Returns the path, or None if it could not be written."""
        try:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "%s.json" % self.run_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.as_dict(), f, indent=2, default=str)
            return path
        except OSError as exc:
            get_logger().warning("could not save trace: %s", exc)
            return None


def _compact(detail: Dict[str, Any], limit: int = 140) -> str:
    if not detail:
        return ""
    text = ", ".join("%s=%s" % (k, v) for k, v in detail.items())
    return text if len(text) <= limit else text[: limit - 3] + "..."
