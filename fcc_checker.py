from system_config import SystemConfig
import os, sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from djutils import logit


def get_album_label(artist_name, album_name):
    if not album_name or len(album_name) == 1:
        return ''

    album_label = ''
    try:
        spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id = SystemConfig.spotify_id,
                client_secret= SystemConfig.spotify_secret
            )
        )

        results = spotify.search(q=f'album:{album_name} artist:{artist_name}', type='album', limit=1)
        if not results["albums"] or not results["albums"]["items"]:
            return None

        item = results['albums']["items"][0]
        album_id = item['id']
        album_info = spotify.album(album_id)
        album_label = album_info['label']

    except Exception as ex:
        logit(f"Exception getting album label from spotify {ex}")

    return album_label


def get_spotify_info(artist, title):
    is_explicit = None
    try:
        spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id = SystemConfig.spotify_id, 
                client_secret= SystemConfig.spotify_secret
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
    except Exception as ex:
        logit(f"Exception getting album explicit from spotify {ex}")

    return is_explicit

def get_lyrics_genius(normalized_artist: str, normalized_title: str) -> str:
    retval = None
    try:
        artist_ar = normalized_artist.split(',')
        primary_artist = normalized_artist if len(artist_ar) < 2 else artist_ar[0]
        genius = lyricsgenius.Genius(SystemConfig.genius_apikey, skip_non_songs=True, remove_section_headers=True)
        song = genius.search_song(
            title=normalized_title,
            artist=primary_artist,
        )
        retval =  song.lyrics if song else None
    except Exception as ex:
        logit(f"Error fetching Genius lyrics {normalized_title}, {ex}")

    return retval


class FCCChecker():
    FCC_STATUS_AR = ['CLEAN', 'DIRTY', 'NOT_FOUND', '-']

    @staticmethod
    def fcc_song_check(artist, title):
        BAD_WORDS = ["shit", "fuck", "asshole", 'nigger']

        lyrics = get_lyrics_genius(artist, title)
        if lyrics:
            lyrics = lyrics.lower()
            for word in BAD_WORDS:
                if word in lyrics:
                    msg = f'Genius explicit: {word}'
                    logit(msg)
                    return FCCChecker.FCC_STATUS_AR[1], msg
    
            return FCCChecker.FCC_STATUS_AR[0], ''

        try:
            explicit = get_spotify_info(artist, title)
            if explicit:
                msg = f'Spotify explicit flag'
                logit(msg)
                return FCCChecker.FCC_STATUS_AR[1], msg
        except Exception as ex:
            logit(f"Error fetching Spotify info {title}, {ex}")


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

