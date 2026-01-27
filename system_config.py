import json
import ssl
import urllib
from  tkinter import messagebox
from djutils import logit

SPOTIFY_ID = ''
SPOTIFY_SECRET = ''
GENIUS_APIKEY = ''
PLAYLIST_APIKEY = ''
PLAYLIST_HOST = 'https://kzsu.stanford.edu'

class SystemConfig():
    spotify_id = SPOTIFY_ID
    spotify_secret = SPOTIFY_SECRET
    genius_apikey = GENIUS_APIKEY
    user_apikey = PLAYLIST_APIKEY
    playlist_host = PLAYLIST_HOST
#    zookeeper_host = ZOOKEEPER_HOST
#    zookeeper_apikey = ZOOKEEPER_APIKEY

    @staticmethod
    def load_config(user_apikey_arg):
        host = PLAYLIST_HOST if PLAYLIST_HOST else 'https://kzsu.stanford.edu'
        if user_apikey_arg:
            SystemConfig.user_apikey = user_apikey_arg

        if host and (not SystemConfig.spotify_id or not SystemConfig.spotify_secret or not SystemConfig.genius_apikey):
            try:
                ssl_context = ssl._create_unverified_context()
                req = urllib.request.Request(host + '/djtool/helpertokens/')
                req.add_header("Content-type", "application/vnd.api+json")
                req.add_header("Accept", "text/plain")
                req.add_header("X-APIKEY", SystemConfig.user_apikey)
                with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                    resp_obj = json.loads(response.read())
                    if not SystemConfig.spotify_id:
                        SystemConfig.spotify_id = resp_obj.get('spotify_id', None)

                    if not SystemConfig.spotify_secret:
                        SystemConfig.spotify_secret = resp_obj.get('spotify_secret', None)

                    if not SystemConfig.genius_apikey:
                        SystemConfig.genius_apikey = resp_obj.get('genius_apikey', None)
            except Exception as e:
                    logit(f"Exception geting apikeys, {e}")
