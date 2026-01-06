import configuration
import os, sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from djutils import logit


def get_spotify_info(artist, title):
    # --- Spotify setup ---
    print(f"ID: {configuration.SPOTIFY_ID}, {configuration.SPOTIFY_SECRET}")

    spotify = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id = configuration.SPOTIFY_ID, 
            client_secret= configuration.SPOTIFY_SECRET
        )
    )

    # Search Spotify to normalize artist/title
    query = f"track:{title} artist:{artist}"
    results = spotify.search(q=query, type="track", limit=1)

    if not results["tracks"]["items"]:
        return None

    track = results["tracks"]["items"][0]
    normalized_title = track["name"]
    normalized_artist = track["artists"][0]["name"]
    is_explicit = track['explicit']
    return is_explicit

#os.environ["GENIUS_ACCESS_TOKEN"],
def get_lyrics_genius(normalized_artist: str, normalized_title: str) -> str:
    genius = lyricsgenius.Genius(configuration.GENIUS_TOKEN, skip_non_songs=True, remove_section_headers=True)

    song = genius.search_song(
        title=normalized_title,
        artist=normalized_artist,
    )

    return song.lyrics if song else None

class FCCChecker():
    FCC_STATUS_AR = ['CLEAN', 'DIRTY', 'NOT_FOUND', '-']

    @staticmethod
    def fcc_song_check(artist, title):
        BAD_WORDS = ["shit", "fuck", "asshole"]
    
        lyrics = get_lyrics_genius(artist, title)
        if lyrics:
            lyrics = lyrics.lower()
            for word in BAD_WORDS:
                if word in lyrics:
                    msg = f'Genius explicit: {word}'
                    logit(msg)
                    return FCCChecker.FCC_STATUS_AR[1], msg
    
            return FCCChecker.FCC_STATUS_AR[0], ''

        explicit = get_spotify_info(artist, title)
        if explicit:
            msg = f'Spotify explicit flag'
            logit(msg)
            return FCCChecker.FCC_STATUS_AR[1], msg

        return FCCChecker.FCC_STATUS_AR[2], ''

if __name__ == "__main__":
   if len(sys.argv) != 3:
        print("Usage: {} <ARTIST> <TRACK>".format(sys.argv[0]))
        sys.exit(1)
   else:
        artist_name = sys.argv[1]
        song_title = sys.argv[2]
        status = FCCChecker.fcc_song_check(artist_name, song_title)
        print(f'{song_title}: {status}')

