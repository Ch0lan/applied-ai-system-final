import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

ACOUSTIC_WEIGHT = 0.5
ACOUSTIC_THRESHOLD = 0.6
MOOD_TAG_WEIGHT = 0.75
LANGUAGE_WEIGHT = 0.5
POPULARITY_WEIGHT = 0.5
EXPLICIT_PENALTY = 1.0
ARTIST_DIVERSITY_PENALTY = 1.0


@dataclass
class ScoringStrategy:
    """A named set of weights for the scoring rule (Strategy pattern)."""
    name: str
    genre_weight: float
    mood_weight: float
    energy_weight: float


STRATEGIES: Dict[str, ScoringStrategy] = {
    "balanced": ScoringStrategy("balanced", genre_weight=2.0, mood_weight=1.0, energy_weight=1.5),
    "genre-first": ScoringStrategy("genre-first", genre_weight=3.0, mood_weight=0.5, energy_weight=1.0),
    "mood-first": ScoringStrategy("mood-first", genre_weight=1.0, mood_weight=2.5, energy_weight=1.0),
    "energy-focused": ScoringStrategy("energy-focused", genre_weight=1.0, mood_weight=0.5, energy_weight=3.0),
}
DEFAULT_STRATEGY = STRATEGIES["balanced"]


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    popularity: float = 50.0
    release_decade: str = "2020s"
    language: str = "english"
    explicit: bool = False
    mood_tag: str = ""


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    favorite_mood_tag: Optional[str] = None
    favorite_language: Optional[str] = None
    target_popularity: Optional[float] = None
    avoid_explicit: bool = False


def _score_components(
    genre: str,
    mood: str,
    energy: float,
    acousticness: float,
    favorite_genre: str,
    favorite_mood: str,
    target_energy: float,
    likes_acoustic: Optional[bool] = None,
    mood_tag: str = "",
    favorite_mood_tag: Optional[str] = None,
    language: str = "",
    favorite_language: Optional[str] = None,
    popularity: Optional[float] = None,
    target_popularity: Optional[float] = None,
    explicit: bool = False,
    avoid_explicit: bool = False,
    strategy: ScoringStrategy = DEFAULT_STRATEGY,
) -> Tuple[float, List[str]]:
    """Shared scoring math used by both the dict pipeline and the OOP Recommender."""
    score = 0.0
    reasons: List[str] = []

    if genre.lower() == favorite_genre.lower():
        score += strategy.genre_weight
        reasons.append(f"genre match (+{strategy.genre_weight:.1f})")

    if mood.lower() == favorite_mood.lower():
        score += strategy.mood_weight
        reasons.append(f"mood match (+{strategy.mood_weight:.1f})")

    energy_points = (1 - abs(energy - target_energy)) * strategy.energy_weight
    if energy_points > 0:
        score += energy_points
        reasons.append(f"energy similarity (+{energy_points:.2f})")

    if likes_acoustic is not None:
        if likes_acoustic and acousticness >= ACOUSTIC_THRESHOLD:
            score += ACOUSTIC_WEIGHT
            reasons.append(f"acoustic match (+{ACOUSTIC_WEIGHT:.1f})")
        elif not likes_acoustic and acousticness >= ACOUSTIC_THRESHOLD:
            score -= ACOUSTIC_WEIGHT
            reasons.append(f"too acoustic for preference (-{ACOUSTIC_WEIGHT:.1f})")

    if favorite_mood_tag and mood_tag and mood_tag.lower() == favorite_mood_tag.lower():
        score += MOOD_TAG_WEIGHT
        reasons.append(f"mood tag match (+{MOOD_TAG_WEIGHT:.2f})")

    if favorite_language and language and language.lower() == favorite_language.lower():
        score += LANGUAGE_WEIGHT
        reasons.append(f"language match (+{LANGUAGE_WEIGHT:.1f})")

    if target_popularity is not None and popularity is not None:
        pop_points = (1 - abs(popularity - target_popularity) / 100) * POPULARITY_WEIGHT
        if pop_points > 0:
            score += pop_points
            reasons.append(f"popularity fit (+{pop_points:.2f})")

    if avoid_explicit and explicit:
        score -= EXPLICIT_PENALTY
        reasons.append(f"explicit content avoided (-{EXPLICIT_PENALTY:.1f})")

    return round(score, 2), reasons


def _apply_diversity_penalty(
    scored: List[Tuple], get_artist, k: int
) -> List[Tuple]:
    """
    Greedily re-rank scored (item, score, reasons) tuples so repeated artists
    are penalized, preventing one artist from dominating the top-k (filter-bubble guard).
    """
    remaining = list(scored)
    selected: List[Tuple] = []
    artist_counts: Dict[str, int] = {}

    while remaining and len(selected) < k:
        best_idx = None
        best_effective = None
        for i, (item, score, reasons) in enumerate(remaining):
            artist = get_artist(item)
            penalty = ARTIST_DIVERSITY_PENALTY * artist_counts.get(artist, 0)
            effective = score - penalty
            if best_effective is None or effective > best_effective:
                best_effective = effective
                best_idx = i

        item, score, reasons = remaining.pop(best_idx)
        artist = get_artist(item)
        count_before = artist_counts.get(artist, 0)
        if count_before > 0:
            penalty = ARTIST_DIVERSITY_PENALTY * count_before
            score = round(score - penalty, 2)
            reasons = reasons + [f"artist diversity penalty (-{penalty:.1f})"]
        artist_counts[artist] = count_before + 1
        selected.append((item, score, reasons))

    return selected


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def _score(self, user: UserProfile, song: Song, strategy: ScoringStrategy) -> Tuple[float, List[str]]:
        return _score_components(
            song.genre, song.mood, song.energy, song.acousticness,
            user.favorite_genre, user.favorite_mood, user.target_energy,
            user.likes_acoustic,
            mood_tag=song.mood_tag, favorite_mood_tag=user.favorite_mood_tag,
            language=song.language, favorite_language=user.favorite_language,
            popularity=song.popularity, target_popularity=user.target_popularity,
            explicit=song.explicit, avoid_explicit=user.avoid_explicit,
            strategy=strategy,
        )

    def recommend(self, user: UserProfile, k: int = 5, mode: str = "balanced") -> List[Song]:
        """Return the top-k songs ranked by score against the user's profile, with an artist-diversity guard."""
        strategy = STRATEGIES.get(mode, DEFAULT_STRATEGY)
        scored = [(song, *self._score(user, song, strategy)) for song in self.songs]
        scored = [(song, score, reasons) for song, score, reasons in scored]
        ranked = _apply_diversity_penalty(scored, get_artist=lambda s: s.artist, k=k)
        return [song for song, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song, mode: str = "balanced") -> str:
        """Return a plain-language reason string for why a song scored as it did."""
        strategy = STRATEGIES.get(mode, DEFAULT_STRATEGY)
        score, reasons = self._score(user, song, strategy)
        if not reasons:
            reasons = ["no strong matches"]
        return f"Score {score:.2f}: " + ", ".join(reasons)


def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file, converting numeric/boolean fields to their proper types."""
    print(f"Loading songs from {csv_path}...")
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["id"] = int(row["id"])
            row["energy"] = float(row["energy"])
            row["tempo_bpm"] = float(row["tempo_bpm"])
            row["valence"] = float(row["valence"])
            row["danceability"] = float(row["danceability"])
            row["acousticness"] = float(row["acousticness"])
            row["popularity"] = float(row.get("popularity", 50) or 50)
            row["explicit"] = str(row.get("explicit", "False")).strip().lower() == "true"
            songs.append(row)
    print(f"Loaded songs: {len(songs)}")
    return songs


def score_song(user_prefs: Dict, song: Dict, mode: str = "balanced") -> Tuple[float, List[str]]:
    """Score a single song dict against a user_prefs dict, returning (score, reasons)."""
    strategy = STRATEGIES.get(mode, DEFAULT_STRATEGY)
    return _score_components(
        song["genre"], song["mood"], song["energy"], song.get("acousticness", 0.0),
        user_prefs["genre"], user_prefs["mood"], user_prefs["energy"],
        user_prefs.get("likes_acoustic"),
        mood_tag=song.get("mood_tag", ""), favorite_mood_tag=user_prefs.get("mood_tag"),
        language=song.get("language", ""), favorite_language=user_prefs.get("language"),
        popularity=song.get("popularity"), target_popularity=user_prefs.get("popularity"),
        explicit=song.get("explicit", False), avoid_explicit=user_prefs.get("avoid_explicit", False),
        strategy=strategy,
    )


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5, mode: str = "balanced") -> List[Tuple[Dict, float, str]]:
    """Score every song, rank by score with an artist-diversity guard, and return the top-k (song, score, explanation) tuples."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, mode=mode)
        scored.append((song, score, reasons))

    ranked = _apply_diversity_penalty(scored, get_artist=lambda s: s["artist"], k=k)
    return [(song, score, ", ".join(reasons) if reasons else "no strong matches") for song, score, reasons in ranked]
