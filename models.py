import datetime, os, ssl
import json
import pathlib
import re
import time
import urllib
import tkinter as tk

import yaml
from pydub import AudioSegment

from  system_config import SystemConfig
from commondefs import *

import pyaudio, os

from djutils import logit
from fcc_checker import get_album_label


class Track():
    PAUSE_FILE = 'PAUSE'
    MIC_BREAK_FILE = 'MIC_BREAK'

    FCC_STATUS_IMAGE = {"CLEAN" : '✅', 'DIRTY': '⛔', 'NOT_FOUND': '✋'}

    def __init__(self, id=-1, fcc_status='', fcc_comment='', artist='', title='', album='',  label='', file_path='', duration=0):
        super().__init__()
        self.id = id
        self.title = title if title else '-'
        self.artist = artist if artist else '-'
        self.album = album if album else '-'
        self.label = label
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

    def album_display(self):
        retval =  f'{self.album} / {self.label}'
        return retval

    def fetch_label(self):
        self.label = get_album_label(self.artist, self.album)

    def have_fcc_status(self):
        have_status = len(self.fcc_status) > 0 and self.fcc_status != '-'
        return have_status

    def fcc_status_glyph(self):
        glyph = self.FCC_STATUS_IMAGE.get(self.fcc_status, self.fcc_status)
        return glyph

    def is_spot_file(self):
        is_spot = self.file_path.startswith("LID_") or self.file_path.startswith('PSA_') or self.file_path.startswith("PROMO_")                 
        return is_spot
                
    def is_audio_file(self):
        is_audio = re.search('audio[0-9]+\\.', self.file_path)
        return is_audio

    def is_stop_file(self):
        return self.title == Track.PAUSE_FILE or self.title == Track.MIC_BREAK_FILE
    
    def is_mic_break_file(self):
        return self.title == Track.MIC_BREAK_FILE
    
    def is_pause_file(self):
        return self.title == Track.PAUSE_FILE
    
    def is_spot_file(self):
        return self.title.startswith("LID_") or self.title.startswith("PSA_") or self.title.startswith("PROMO_")

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

    @staticmethod
    def HM_from_float(float_time):
        hour = int(float_time)
        mins = int((float_time - hour) * 60)
        suffix = 'pm' if hour >= 12 else 'am'
        if hour == 0:
            hour = 12
        elif hour > 12:
            hour = hour - 12

        retval = f'{hour}{suffix}' if mins == 0 else f'{hour}:{mins:02d} {suffix}'
        return retval

    # return true if playlist is active and within start/end window
    def _is_active(self):
        is_active = False
        #TODO add minutes
        if self.id:
            now_date = datetime.datetime.now()
            now_hour = now_date.hour + now_date.minute / 60
            if self.end_hour > self.start_hour:
                is_active = self.start_hour <= now_hour  <= self.end_hour
            else:
                is_active = now_hour >= self.start_hour or now_hour < self.end_hour

        return is_active

    def send_track_zookeeper(self, track):
        start_time = time.time_ns()
        if not self.id or not self._is_active() or track.is_pause_file() or track.title.startswith("LID_"):
            logit(f"skip send_track {self.id}, {self._is_active()}")
            return

        url = SystemConfig.zookeeper_host + f'/api/v2/playlist/{self.id}/events'
        method = "POST"  # timestamp this track
        event_type = 'break' if track.is_mic_break_file() else 'spin'
        event = {
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

        data = {"data": event}
        data_json = json.dumps(data)
        req = urllib.request.Request(url, method=f'{method}')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", SystemConfig.zookeeper_apikey)

        try:
            with urllib.request.urlopen(req, data=data_json.encode('utf-8'), timeout=ZOOKEEPER_TIMEOUT_SECONDS,
                                        context=self.ssl_context) as response:
                resp_obj = json.loads(response.read())
        except Exception as e:
            logit(f"Exception posting track: {url}, {e}")

        end_time = time.time_ns()

    def send_track(self, track):
        start_time = time.time_ns()
        if not self.id or not self._is_active() or track.is_pause_file() or track.title.startswith("LID_"):
            logit(f"skip send_track {self.id}, {self._is_active()}")
            return

        url = SystemConfig.playlist_host + f'/djtool/addtrack/'
        apikey = SystemConfig.user_apikey
        event_type = 'break' if track.is_mic_break_file() else 'spin'
        data =  {
                "id": self.id,
                "type": event_type,
                "created": "auto",
                "artist": track.artist,
                "track": track.title,
                "album": track.album,
                "label": '-'
        }

        data_json = json.dumps(data)
        req = urllib.request.Request(url, method=f'POST')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", apikey)
        
        try:
            with urllib.request.urlopen(req, data=data_json.encode('utf-8'), timeout=2, context=self.ssl_context) as response:
                resp_obj  = json.loads(response.read())
        except Exception as e:
            logit(f"Exception posting track: {url}, {e}")


    def check_show_playlist(self, target_title):
        apikey = SystemConfig.user_apikey
        if not apikey:
            tk.messagebox.showwarning("Missing User Key", "The User API Key must be set using File->Configuration in order to use this feature.")
            return False

        self.id = None
        title_safe = urllib.parse.quote(target_title)
        url = SystemConfig.playlist_host + f'/djtool/showplaylist/?show_title={title_safe}'
        req = urllib.request.Request(url, method=f'GET')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", apikey)

        try:
            with urllib.request.urlopen(req, timeout=2, context=self.ssl_context) as response:
                playlist  = json.loads(response.read())
                if 'id' in playlist:
                    self.id = playlist['id']
                    self.start_hour = playlist['start_time']
                    self.end_hour = playlist['end_time']
                    start_str = self.HM_from_float(self.start_hour)
                    end_str = self.HM_from_float(self.end_hour)
                    msg = f'Playlist found. Track spins will be logged to your show between {start_str} and {end_str}, {self.id}'
                    tk.messagebox.showwarning(title="Info", message=msg)
        except Exception as e:
            logit(f"Exception getting playlist: {url}, {e})")
            msg = f"Exception while checking playlist. Use File->Configuration to check that your user api key is correct. {e}, {url}"
            tk.messagebox.showwarning(title="Error", message=msg, parent=self.parent)
            return False


        if not self.id:
            self.parent.live_show.set(False)
            tk.messagebox.showwarning(title="Error", message=f"Zookeeper playlist '{target_title}' not found.", parent=self.parent)
          
        return self.id != None

    def check_show_playlist_zookeeper(self, target_title):
        self.id = None
        now_date = datetime.datetime.now().date().isoformat()
        now_date = '2026-01-31'  ##############
        url = SystemConfig.zookeeper_host + f'/api/v2/playlist?filter[date]={now_date}'

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
                         start_str = self.HM_from_float(self.start_hour)
                         end_str = self.HM_from_float(self.end_hour)
                         msg = f'Playlist found. Track spins will be logged to your show between {start_str} and {end_str}, {self.id}'
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
    show_title = ''
    show_start_time = ''
    playlist_host = ''
    user_apikey = ''

    @staticmethod
    def load_config():
        config_dict = {}
        try:
            with open(UserConfiguration.CONFIG_FILE, 'r') as file:
                config_dict = yaml.safe_load(file)
        except IOError:
            pass

        UserConfiguration.show_title = config_dict.get('show_title', '')
        UserConfiguration.show_start_time = config_dict.get('show_start_time', 0)
        UserConfiguration.playlist_host = config_dict.get('playlist_host', '')
        UserConfiguration.user_apikey = config_dict.get('user_apikey', '')

    @staticmethod
    def save_config():
        data = {
            "show_title" : UserConfiguration.show_title,
            "show_start_time": UserConfiguration.show_start_time,
            "user_apikey": UserConfiguration.user_apikey
        }
        yaml_string = yaml.dump(data, sort_keys=False)

        try:
            with open(UserConfiguration.CONFIG_FILE, 'w') as file:
                file.write(yaml_string)
        except IOError:
            logit("Error saving configuration file: {ex}")


    @staticmethod
    def get_show_start_seconds():
        seconds = 0
        time_ar = UserConfiguration.show_start_time.split(' ')
        if len(time_ar) == 2:
            suffix = time_ar[1]
            hour = int(time_ar[0])
            if hour == 12 and suffix == 'am':
                hour = 0
            elif hour != 12 and suffix == 'pm':
                hour = hour + 12

            seconds = hour * 3600

        return seconds


