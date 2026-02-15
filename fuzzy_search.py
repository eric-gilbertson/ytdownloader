from ytmusicapi import YTMusic
from rapidfuzz import fuzz
import re, sys
import unicodedata

# uses rapidfuzz to find and rank queries with misspelled artist and song names.

class FuzzyYTMusic:
    def __init__(self, auth_file=None):
        """
        auth_file: path to headers_auth.json if required
        """
        self.yt = YTMusic(auth_file) if auth_file else YTMusic()

    # --------------------------
    # Normalization utilities
    # --------------------------

    @staticmethod
    def normalize(text):
        """
        Lowercase, strip accents, remove punctuation, collapse whitespace.
        """
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # --------------------------
    # Similarity scoring
    # --------------------------

    def score_candidate(self, result, target_artist, target_title):
        """
        Compute combined similarity score between target and result.
        """
        result_title = self.normalize(result.get("title", ""))
        result_artist = self.normalize(
            result.get("artists", [{}])[0].get("name", "")
        )

        title_score = fuzz.token_set_ratio(result_title, target_title)
        artist_score = fuzz.token_set_ratio(result_artist, target_artist)

        # Weight title slightly higher than artist
        combined = (0.6 * title_score) + (0.4 * artist_score)
        return combined

    # --------------------------
    # Fuzzy search wrapper
    # --------------------------

    def search_song(self, artist, title, limit=10, min_score=70):
        """
        Returns best matching song result dict or None.
        """

        target_artist = self.normalize(artist)
        target_title = self.normalize(title)

        # Initial query
        query = f"{artist} {title}"
        print("query: " + query)
        results = self.yt.search(query, filter="songs", limit=limit)

        candidates = []

        for result in results:
            score = self.score_candidate(result, target_artist, target_title)
            candidates.append((score, result))

        # If nothing found, try looser query strategies
        if not candidates or max(c[0] for c in candidates) < min_score:
            fallback_queries = [
                title,              # title only
                artist,             # artist only
                f"{title} {artist}" # reversed order
            ]

            for q in fallback_queries:
                results = self.yt.search(q, filter="songs", limit=limit)
                for result in results:
                    score = self.score_candidate(result, target_artist, target_title)
                    candidates.append((score, result))

        if not candidates:
            return None

        # Sort descending by similarity
        candidates.sort(key=lambda x: x[0], reverse=True)
        tracks = [item[1] for item in candidates]
        return tracks


# --------------------------
# Example usage
# --------------------------

if __name__ == "__main__":
    fyt = FuzzyYTMusic()

    if len(sys.argv) < 2:
        print("Usage: <ARTIST> <TITLE> [<ALBUM>]")
        sys.exit(0)

    artist = sys.argv[1]
    track = sys.argv[2]
    album = sys.argv[3] if len(sys.argv) > 3 else ''

    results = fyt.search_song(artist, track)

    if len(results) > 0:
        for result in results:
            print(f"hit: {result[0]}, {result[1]['title']}, {result[1]['artists'][0]['name']}, {result[1]['album']['name']}")
    else:
        print("No sufficiently close match found.")

