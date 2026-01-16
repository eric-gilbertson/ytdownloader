import datetime, os, ssl
import json
import pathlib
import time
import urllib
import tkinter as tk

import yaml
from pydub import AudioSegment

import configuration
from commondefs import *

import pyaudio, os

from djutils import logit


class Track():
    FCC_STATUS_IMAGE = {"CLEAN" : '✅', 'DIRTY': '⛔', 'NOT_FOUND': '✋'}

    def __init__(self, id=-1, fcc_status='', fcc_comment='', artist='', title='', album='',  file_path='', duration=0):
        super().__init__()
        self.id = id
        self.title = title if title else '-'
        self.artist = artist if artist else '-'
        self.album = album if album else '-'
        self.file_path = file_path
        self.duration = duration # seconds
        self.fcc_status = fcc_status if fcc_status else ''
        self.fcc_comment = fcc_comment if fcc_comment else ''

        if duration <= 0:
            if os.path.exists(file_path):
                self.duration = len(AudioSegment.from_file(file_path))/1000
            else:
                self.duration = 0

    def to_dict(self):
        dict = self.__dict__
        return dict

    def have_fcc_status(self):
        have_status = len(self.fcc_status) > 0 and self.fcc_status != '-'
        return have_status

    def fcc_status_glyph(self):
        glyph = self.FCC_STATUS_IMAGE.get(self.fcc_status, self.fcc_status)
        return glyph

    @staticmethod
    def from_dict(track_dict):
        track = Track()
        for key, val in track_dict.items():
            setattr(track, key, val)

        return track

class ZKPlaylist():
    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.track_idx = 0
        self.id = None
        self.start_hour = 0.0
        self.end_hour = 0.0
        self.ssl_context = ssl._create_unverified_context()

    # return true if playlist is active and within start/end window
    def _is_active(self):
        is_active = False
        if self.id:
            now_date = datetime.datetime.now()
            now_hour = now_date.hour + now_date.minute / 60
            if self.end_hour > self.start_hour:
                is_active = self.start_hour <= now_hour  <= self.end_hour
            else:
                is_active = now_hour >= self.start_hour or now_hour < self.end_hour

        return is_active

    def send_track(self, track):
        start_time = time.time_ns()
        if not self.id or not self._is_active() or is_pause_file(track.title) or track.title.startswith("LID_"):
            logit(f"abort send_track {self.id}")
            return

        url = self.parent.configuration.zookeeper_url + f'/api/v2/playlist/{self.id}/events'
        method = "POST" # timestamp this track
        event_type = 'break' if is_mic_break_file(track.title) else 'spin'
        event =  {
            "type": "event",
            "attributes": {
                "type": event_type,
                "created": "auto",
                "artist": track.artist,
                "track": track.title,
                "album": track.album,
                "label": '-'
             }
        }

        data = {"data" : event}
        data_json = json.dumps(data)
        req = urllib.request.Request(url, method=f'{method}')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", self.parent.configuration.zookeeper_api)
        
        try:
            with urllib.request.urlopen(req, data=data_json.encode('utf-8'), timeout=ZOOKEEPER_TIMEOUT_SECONDS, context=self.ssl_context) as response:
                resp_obj  = json.loads(response.read())
        except Exception as e:
            logit(f"Exception posting track: {url}, {e}")

        end_time = time.time_ns()

    def check_show_playlist(self, target_title):
        self.id = None
        now_date = datetime.datetime.now().date().isoformat()
        url = self.parent.configuration.zookeeper_url + f'/api/v2/playlist?filter[date]={now_date}'

        try:
            target_title_lc = target_title.lower()
            with urllib.request.urlopen(url, timeout=ZOOKEEPER_TIMEOUT_SECONDS, context=self.ssl_context) as response:
                playlists  = json.loads(response.read())['data']
                for  playlist in playlists:
                     attrs = playlist['attributes']
                     if attrs['name'].lower() == target_title_lc:
                         self.id = playlist['id']
                         time_ar = attrs['time'].split('-')
                         self.start_hour = float(time_ar[0][:2]) + (int(time_ar[0][2:4]) / 60.0)
                         self.end_hour = float(time_ar[1][:2]) + (int(time_ar[1][2:4]) / 60.0)
                         msg = f'Playlist found. Track spins will be logged to {target_title} between {time_ar[0]} and {time_ar[1]}, {self.id}'
                         tk.messagebox.showwarning(title="Info", message=msg)
                         break
                      
        except Exception as e:
            logit(f"Exception getting playlist: {url}, {e})")

        if not self.id:
            self.parent.live_show.set(False)
            tk.messagebox.showwarning(title="Error", message=f"Zookeeper playlist '{target_title}' not found.", parent=self.parent)
          
        return self.id != None


class UserConfiguration():
    CONFIG_FILE = f'{pathlib.Path.home()}/.djtool.yaml'

    def __init__(self, config_dict):
        self.show_title = config_dict.get('show_title', '')
        self.show_start_time = config_dict.get('show_start_time', 0)
        self.zookeeper_url = config_dict.get('zookeeper_url', 'https://zookeeper.stanford.edu')
        self.zookeeper_api = configuration.ZOOKEEPER_API
        self.apikey = config_dict.get('api_key', '')
        self.genius_api = configuration.GENIUS_TOKEN
        self.spotify_id = configuration.SPOTIFY_ID
        self.spotify_secret = configuration.SPOTIFY_SECRET

    def have_apikeys(self):
        retval = self.zookeeper_api and self.genius_api and self.spotify_id and self.spotify_secret
        return retval

    def to_dict(self):
        dict = {
            'show_title' : self.show_title,
        }
        return dict

    def to_yaml(self):
        data = self.to_dict()
        yaml_string = yaml.dump(data, sort_keys=False)
        return yaml_string

    @staticmethod
    def load_config():
        config_yaml = {}
        try:
            with open(UserConfiguration.CONFIG_FILE, 'r') as file:
                config_yaml = yaml.safe_load(file)
        except IOError:
            pass

        config = UserConfiguration(config_yaml)
        return config

    def save_config(self):
        yaml = self.to_yaml()
        try:
            with open(UserConfiguration.CONFIG_FILE, 'w') as file:
                file.write(yaml)
        except IOError:
            logit("Error saving configuration file: {ex}")

    def set_apikeys(self):
        if not self.have_apikeys():
            if not self.apikey:
                tk.messagebox.showwarning(title="Info",
                                          message="API keys not found. Not all functions will be available")
            else:
                try:
                    ssl_context = ssl._create_unverified_context()
                    # req = urllib.request.Request('https://kzsu/stanford.edu/internal/apikeys') #####
                    req = urllib.request.Request('http://localhost:5000/internal/helpertokens/')
                    req.add_header("Content-type", "application/vnd.api+json")
                    req.add_header("Accept", "text/plain")
                    req.add_header("X-APIKEY", self.apikey)
                    with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:

                        resp_obj = json.loads(response.read())
                        self.spotify_id = resp_obj.get('spotify_id', None)
                        self.spotify_secret = resp_obj.get('spotify_secret', None)
                        self.genius_api = resp_obj.get('genius_apikey', None)
                        self.zookeeper_api = resp_obj.get('zookeeper_apikey', None)
                except Exception as e:
                    logit(f"Exception geting apikeys, {e}")

