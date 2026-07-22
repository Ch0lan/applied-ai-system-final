"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from tabulate import tabulate

from src.recommender import load_songs, recommend_songs, STRATEGIES

PROFILES = {
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.8},
    "Chill Lofi": {"genre": "lofi", "mood": "chill", "energy": 0.35},
    "Deep Intense Rock": {"genre": "rock", "mood": "intense", "energy": 0.9},
    "Conflicted Listener": {"genre": "metal", "mood": "sad", "energy": 0.9},
}


def print_table(profile_name: str, user_prefs: dict, songs: list, k: int = 5, mode: str = "balanced") -> None:
    recommendations = recommend_songs(user_prefs, songs, k=k, mode=mode)
    rows = [
        [song["title"], song["artist"], f"{score:.2f}", explanation]
        for song, score, explanation in recommendations
    ]
    print(f"\n=== {profile_name} | mode={mode} | prefs: {user_prefs} ===\n")
    print(tabulate(rows, headers=["Title", "Artist", "Score", "Reasons"], tablefmt="grid"))


def main() -> None:
    songs = load_songs("data/songs.csv")

    for profile_name, user_prefs in PROFILES.items():
        print_table(profile_name, user_prefs, songs, k=5)

    # Demonstrate the Strategy pattern: same profile, different ranking modes.
    print("\n\n--- Ranking mode comparison for 'High-Energy Pop' ---")
    for mode in STRATEGIES:
        print_table("High-Energy Pop", PROFILES["High-Energy Pop"], songs, k=3, mode=mode)


if __name__ == "__main__":
    main()
