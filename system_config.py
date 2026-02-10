import json
import ssl
import tkinter.messagebox
import urllib
from  tkinter import messagebox
from djutils import logit

SPOTIFY_ID = ''
SPOTIFY_SECRET = ''
GENIUS_APIKEY = ''
PLAYLIST_APIKEY = '8v3TC5vf8zVpwUuQ0K4uCz7kYBcTZj7i'
PLAYLIST_HOST = 'http://localhost:5000'
OUTPUT_DEVICE = ''

class SystemConfig():
    spotify_id = SPOTIFY_ID
    spotify_secret = SPOTIFY_SECRET
    genius_apikey = GENIUS_APIKEY
    user_apikey = PLAYLIST_APIKEY
    playlist_host = PLAYLIST_HOST
    output_device = OUTPUT_DEVICE

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
                msg = '''FCC checking and album lookup are not available because the helper keylookup failed.  Check that your user key in the File->Configuration dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''
                tkinter.messagebox.showwarning("Configuration Error", msg)

    @staticmethod
    def check_have_user_key():
        msg = None
        if not SystemConfig.user_apikey:
            msg = '''This feature is not be available because your user
                apikey has not been set. Set it by visiting https://kzsu.stanford.edu/internal/profile
                and clicking the Add Key button. Then copy the generated key and paste it into the User API Key
                field in the user configuration dialog which is accessed by clicking File->Configure...'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg

    @staticmethod
    def check_have_spotify_key():
        msg = None
        if not SystemConfig.spotify_id or not SystemConfig.spotify_secret:
            msg = '''This feature is not available because the Spotify
                 apikeys have not been set. Check that your user key in the File->Configuration
                 dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg

    def check_have_genius_key():
        msg = None
        if not SystemConfig.genius_apikey:
            msg = '''This feature is not available because the Genius
                 apikey has not been set. Check that your user key in the File->Configuration
                 dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg
