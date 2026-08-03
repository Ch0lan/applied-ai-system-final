"""
Retrieval layer (the "R" in RAG).

Indexes a corpus of listening-context documents and returns the ones most relevant
to a free-text request. Retrieval is pure Python (BM25 over a token index) so the
system is reproducible offline with no API key and no vector-database service.

Two sources are indexed together:
  - data/knowledge/       the shared listening-context corpus
  - data/knowledge_user/  per-user notes, which may declare `source_weight` to
                          outrank the general corpus on the same query
"""

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# BM25 parameters. k1 controls term-frequency saturation, b controls length normalization.
BM25_K1 = 1.5
BM25_B = 0.75

# Tags are the highest-signal field in a document, so their tokens are repeated in the
# index to weight them above body prose without needing a full field-weighted BM25.
TAG_BOOST = 3
TITLE_BOOST = 2

_TOKEN_RE = re.compile(r"[a-z0-9']+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "to", "of", "in", "on", "at", "is",
    "it", "its", "with", "that", "this", "i", "im", "me", "my", "some", "something",
    "want", "need", "give", "get", "please", "can", "you", "would", "like", "am",
    "be", "do", "have", "has", "was", "were", "so", "as", "if", "then", "than",
}

_FLOAT_FIELDS = {"energy", "source_weight"}
_BOOL_FIELDS = {"likes_acoustic", "avoid_explicit"}


def tokenize(text: str) -> List[str]:
    """Lowercase, split on non-word characters, drop stopwords and 1-character tokens."""
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 1
    ]


@dataclass
class Document:
    """One knowledge-base document: front-matter cues plus indexed prose."""
    doc_id: str
    title: str
    tags: List[str]
    body: str
    source: str
    cues: Dict[str, object] = field(default_factory=dict)
    source_weight: float = 1.0
    tokens: List[str] = field(default_factory=list)

    @property
    def snippet(self) -> str:
        """First paragraph of the body, used when showing evidence to the user."""
        for para in self.body.split("\n\n"):
            cleaned = " ".join(para.split())
            if cleaned:
                return cleaned
        return ""


class RetrievalError(Exception):
    """Raised when the corpus cannot be loaded or is empty."""


def _coerce(key: str, raw: str):
    if key in _FLOAT_FIELDS:
        try:
            return float(raw)
        except ValueError:
            return None
    if key in _BOOL_FIELDS:
        return raw.strip().lower() in ("true", "yes", "1")
    return raw.strip()


def parse_document(text: str, source: str, fallback_id: str) -> Optional[Document]:
    """
    Parse a markdown file with `---` delimited front matter into a Document.
    Returns None for files without front matter (e.g. a source README).
    """
    if not text.lstrip().startswith("---"):
        return None

    stripped = text.lstrip()
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return None

    front, body = parts[1], parts[2]

    meta: Dict[str, str] = {}
    for line in front.strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip()

    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]

    cues: Dict[str, object] = {}
    for key in ("genre", "mood", "energy", "likes_acoustic", "avoid_explicit", "language", "strategy"):
        if key in meta:
            value = _coerce(key, meta[key])
            if value is not None and value != "":
                cues[key] = value

    doc = Document(
        doc_id=meta.get("id", fallback_id),
        title=meta.get("title", fallback_id),
        tags=tags,
        body=body.strip(),
        source=source,
        cues=cues,
        source_weight=float(meta.get("source_weight", 1.0) or 1.0),
    )
    doc.tokens = (
        tokenize(" ".join(tags)) * TAG_BOOST
        + tokenize(doc.title) * TITLE_BOOST
        + tokenize(doc.body)
    )
    return doc


def load_documents(directories: Iterable[str]) -> List[Document]:
    """Load every front-matter markdown file from the given directories."""
    docs: List[Document] = []
    for directory in directories:
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            doc = parse_document(text, source=directory, fallback_id=name[:-3])
            if doc is not None:
                docs.append(doc)
    return docs


class KnowledgeRetriever:
    """BM25 retriever over the listening-context corpus."""

    def __init__(self, documents: List[Document]):
        if not documents:
            raise RetrievalError("knowledge corpus is empty - nothing to retrieve from")
        self.documents = documents
        self._doc_freq: Counter = Counter()
        self._term_freqs: List[Counter] = []
        for doc in documents:
            tf = Counter(doc.tokens)
            self._term_freqs.append(tf)
            for term in tf:
                self._doc_freq[term] += 1
        lengths = [len(d.tokens) for d in documents]
        self._avg_len = sum(lengths) / len(lengths)

    @classmethod
    def from_directories(cls, directories: Iterable[str]) -> "KnowledgeRetriever":
        return cls(load_documents(directories))

    def _idf(self, term: str) -> float:
        n = len(self.documents)
        df = self._doc_freq.get(term, 0)
        # BM25 idf with +1 smoothing so common terms stay non-negative.
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: List[str], index: int) -> float:
        tf = self._term_freqs[index]
        doc_len = len(self.documents[index].tokens)
        total = 0.0
        for term in query_tokens:
            freq = tf.get(term, 0)
            if not freq:
                continue
            numerator = freq * (BM25_K1 + 1)
            denominator = freq + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / self._avg_len)
            total += self._idf(term) * numerator / denominator
        return total * self.documents[index].source_weight

    def retrieve(self, query: str, k: int = 3) -> List[Tuple[Document, float]]:
        """Return the top-k (document, score) pairs, dropping zero-score documents."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored = [
            (self.documents[i], self.score(query_tokens, i))
            for i in range(len(self.documents))
        ]
        scored = [(doc, s) for doc, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]

    def describe_sources(self) -> Dict[str, int]:
        """Document count per source directory, for `--show-sources`."""
        counts: Dict[str, int] = {}
        for doc in self.documents:
            counts[doc.source] = counts.get(doc.source, 0) + 1
        return counts
