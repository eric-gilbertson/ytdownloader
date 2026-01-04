# asynchromously downloads a track using yt-dlp and performs name cleanup on the downloaded file.
#
import threading, subprocess, shutil, re, os
from pathlib import Path
from tkinter import simpledialog
import tkinter as tk
from tkinter import messagebox
from ytmusicapi import YTMusic


from audio_trimmer import trim_audio
from djutils import logit

FIELD_SEPARATOR = '^'

class CommandThread(threading.Thread):
    def __init__(self, cmd, done_callback):
        super(CommandThread, self).__init__()
        self.done_callback = done_callback
        self.cmd = cmd
        self.process = None
        self.stdout = None
        self.stderr = None

    def run(self):
        self.process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (self.stdout, self.stderr) = self.process.communicate()
        self.done_callback()
        pass

class Track():
    def __init__(self, id, artist, title, album,  track_file, duration):
        super().__init__()
        self.id = id
        self.title = title
        self.artist = artist
        self.album = album
        self.track_file = track_file
        self.duration = duration # seconds

class TrackDownloader():
    def __init__(self, download_dir):
        self.YTDL_PATH = shutil.which('yt-dlp')
        self.download_dir = download_dir
        self.download_thread = None
        self.name_too_long = False
        self.err_msg = ''
        self.track = Track('', '', '', '', '', 0)
        self.track_url = ''
        self.track_file = None
        self.track_album = ''
        self.is_done = False

        if not os.path.exists(download_dir):
            os.makedirs(download_dir)


    def fetch_track(self, parent, track_specifier, use_fullname):
        logit(f"Enter fetch_track: {track_specifier}")
        ARTIST_TRACK_SEPARATOR = r'[;\t]' # split on ; and <tab>
        artistTerm = '%(artist)s' if use_fullname  else 'UNKNOWN'
        out_file = '"{}/{}_%(title)s.%(ext)s"'.format(self.download_dir, artistTerm)
        self.track_album = ''

        track_specifier_ar = re.split(ARTIST_TRACK_SEPARATOR, track_specifier)
        # use_fullname is false when the first try fails because the artist name was too long
        # for the filename. if a second try then skip the track lookup and use the previous URL.
        if use_fullname  and len(track_specifier_ar) == 2:
            artist = track_specifier_ar[0]
            title = track_specifier_ar[1]
            tracks = getTracksYouTube(artist, title)
            if len(tracks) == 0:
                tk.messagebox.showwarning(title="Error", message=f"Nothing found for -{title}- by -{artist}-")
                return False
            else:
                dialog = SelectTrackDialog(parent, artist, title, tracks)
                if not dialog.ok_clicked or len(dialog.track_id) == 0:
                    return False

                self.track_album = dialog.album
                self.track_url = f"https://youtube.com/watch?v={dialog.track_id}"
        elif use_fullname:
            self.track_url = track_specifier

        if not "youtube.com/watch?" in self.track_url:
            tk.messagebox.showwarning(title="Error", message=f"Invalid request entry. Use either a Youtube watch URL, e.g. youtube.com/watch?=<SOME_ID> or <ARTIST_NAME>;<SONG_TITLE>")
            return False

        cmd = self.YTDL_PATH + ' --extract-audio --audio-format wav -o {} {}'.format(out_file, self.track_url)
        self.is_done = False
        self.download_thread = CommandThread(cmd, self.on_fetch_done)
        self.download_thread.start()
        return True

    def on_fetch_done(self):
        self.err_msg = str(self.download_thread.stderr)

        if self.err_msg.find('File name too long') > 0:
            self.name_too_long = True
        elif self.download_thread.process.returncode == 0:
            stdOut = self.download_thread.stdout.decode('UTF-8')
            idx1 = stdOut.rfind("Destination: ") + 13
            idx2 = stdOut.find(".wav", idx1)
            if idx1 > 13 and idx2 > idx1:
                self.errMsg = ''
                self.track.track_file =  stdOut[idx1:idx2+4]
                logit("Downloaded file: " + self.track.track_file)
                self.track.album = self.track_album
                (self.track.track_file, self.track.artist, self.track.title)  = self.clean_filepath(self.track.track_file)
                trim_audio(self.track.track_file)

        self.is_done = True


    # normalizes files downloaded from YT & MPE into standard <ARTIST>^<TITLE> name format.
    @staticmethod
    def clean_filepath(filepath):
        new_name_ext = os.path.basename(filepath)
        new_name, name_extension = os.path.splitext(new_name_ext)
    
        if not (filepath.endswith('.wav') or filepath.endswith(".mp3")):
            return (filepath, '', '')
    
        # remove parenthetical and bracketed text
        new_name = re.sub(r"[\(\[\{].*?[\)\]\}]", "", new_name)
        new_name = re.sub(r'- \d+ -', FIELD_SEPARATOR, new_name)

        # replace quoted song with seperator, e.g. John Craige "Judias"
        WIERD_QUOTE = '＂'
        if new_name.find(WIERD_QUOTE) > 0:
            new_name = new_name.replace(WIERD_QUOTE, FIELD_SEPARATOR, 1)
            new_name = new_name.replace(WIERD_QUOTE, '', 1)
    
        if new_name.find('Official Track') >= 0:
            new_name = new_name.replace('Official Track', '')
    
        if new_name.find('Official Lyric Video') >= 0:
            new_name = new_name.replace('Official Lyric Video', '')
    
        if new_name.find('Lyric Video') >= 0:
            new_name = new_name.replace('Lyric Video', '')
    
        if new_name.find('OFFICIAL MUSIC VIDEO') >= 0:
            new_name = new_name.replace('OFFICIAL MUSIC VIDEO', '')
    
        if new_name.find('NA_') >= 0:
            new_name = new_name.replace('NA_', '')
    
        if new_name.find('｜') >= 0:
            new_name = new_name.replace('｜', FIELD_SEPARATOR)
    
        if new_name.find(' : ') >= 0:
            new_name = new_name.replace(' : ', FIELD_SEPARATOR)
    
        if new_name.find('＂') >= 0:  # special fat double quote from &quot; in html
            new_name = new_name.replace('＂', '')
    
        if new_name.find('"') >= 0:  # regular double quote
            new_name = new_name.replace('"', '')
    
        if new_name.find('-') >= 0:
            new_name = new_name.replace('-', FIELD_SEPARATOR)
    
        if new_name.find('_') >= 0:
            new_name = new_name.replace('_', ' ' + FIELD_SEPARATOR + ' ')
    
        if new_name.find('–') >= 0:
            new_name = new_name.replace('–', FIELD_SEPARATOR)
    
        if new_name.find('Official HD Audio') >= 0:  # regular double quote
            new_name = new_name.replace(' Official HD Audio', '')
    
        if new_name.find('Official Music Video') >= 0:  # regular double quote
            new_name = new_name.replace(' Official Music Video', '')
    
        if new_name.find(f"{FIELD_SEPARATOR} {FIELD_SEPARATOR}") >= 0:
            new_name = new_name.replace(f"{FIELD_SEPARATOR} {FIELD_SEPARATOR}", FIELD_SEPARATOR)
    
        if new_name.find(f"{FIELD_SEPARATOR} .") >= 0:
            new_name = new_name.replace(f"{FIELD_SEPARATOR} .", ".")
    
        namesAr = new_name.split(FIELD_SEPARATOR)
        commaIdx = namesAr[0].find(',')
        artist = namesAr[0].strip() if commaIdx < 0 else namesAr[0][0:commaIdx].strip()
        title = os.path.splitext(namesAr[1])[0].strip() if len(namesAr) > 1 else ''
        new_file = f"{os.path.dirname(filepath)}/{new_name}{name_extension}"

        if new_file != filepath:
            os.rename(filepath, new_file)
    
        Path(new_file).touch()
        return (new_file, artist, title)

    def edit_track(self, parent, track):
        dialog = TrackEditDialog(parent, "Edit Track",
                                 track.artist,
                                 track.title,
                                 track.album)

        if dialog.ok_clicked:
            #self.is_dirty = True
            track.artist = dialog.track_artist
            track.title = dialog.track_title
            track.album = dialog.track_album
            unused, suffix = os.path.splitext(track.track_file)

            new_file = f"{os.path.dirname(track.track_file)}/{track.artist} {FIELD_SEPARATOR} {track.title}{suffix}"
            os.rename(track.track_file, new_file)
            track.track_file = new_file

            #row_values = self.tree.item(track.id)["values"]
            #row_values = (*row_values[0:2], track.artist, track.title, track.album)
            #self.tree.item(track.id, values=row_values)
            return True
        else:
            return False


class SelectTrackDialog(simpledialog.Dialog):
    def __init__(self, parent, artist, track_title, track_choices):
        # store initial values
        self.artist = artist
        self.track_title = track_title
        self.album = ''
        self.track_choices = track_choices
        self.track_id = ''
        self.ok_clicked = False
        super().__init__(parent, title='Select Song')

    def body(self, master):
        self.choices_entry = tk.Text(master, borderwidth=1, relief="solid", width=80)
        self.choices_entry.bind("<Double-1>", lambda e: self._select_row(e))
        self.choices_entry.config(cursor="arrow")

        self.choice_entry = tk.Entry(master, width=60)
        self.track_info = tk.Entry(master, width=60)

        idx = 1
        tracks = ''
        for track in self.track_choices:
            tracks = tracks + f"{idx}: {track['duration']} {track['title']} - {track['artists'][0]['name']} - {track['album']['name']}\n"
            idx = idx + 1

        self.choices_entry.insert("1.0", tracks)
        self.track_info.insert(0, f'{self.artist} - {self.track_title}')

        if idx > 1:
            self.choice_entry.insert(0, '1')

        self.choice_entry.focus_set()
 
        # Place widgets
        self.track_info.grid(row=1, column=0, padx=0, pady=5)
        self.choices_entry.grid(row=2, column=0, padx=0, pady=5)
        self.choice_entry.grid(row=3, column=0, padx=5, pady=5)

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True

        choice = self.choice_entry.get()
        if len(choice) == 0:
            self.ok_clicked = False
        elif len(choice) == 1:
            choice_num = int(choice) - 1
            self.track_id = self.track_choices[choice_num]['videoId']

    def _select_row(self, event):
        index = self.choices_entry.index(f"@{event.x},{event.y}")
        line_number = int(index.split('.')[0]) - 1
        if line_number >= len(self.track_choices):
            return

        self.ok_clicked = True
        self.track_id = self.track_choices[line_number]['videoId']
        self.album = self.track_choices[line_number]['album']['name']
        self.destroy()
    
class TrackEditDialog(simpledialog.Dialog):
    def __init__(self, parent, hdr_title=None, track_artist="", track_title="", track_album=""):

        # store initial values
        self.initial_artist = track_artist
        self.initial_title = track_title
        self.initial_album = track_album
        self.ok_clicked = False
        self.track_artist = ""
        self.track_title  = ""
        self.track_album = ""
        super().__init__(parent, hdr_title)

    def body(self, master):
        #self.transient(master)  # stay on top of parent
        #self.grab_set_global()              # capture all events to this dialog

        # Create labels
        tk.Label(master, text="Artist:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Album:").grid(row=2, column=0, sticky="e", padx=5, pady=5)

        # Create entry fields with initial values
        self.artist_entry = tk.Entry(master, width=40)
        self.artist_entry.insert(0, self.initial_artist)

        self.title_entry = tk.Entry(master, width=40)
        self.title_entry.insert(0, self.initial_title)

        self.album_entry = tk.Entry(master, width=40)
        self.album_entry.insert(0, self.initial_album)

        # Place widgets
        self.artist_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.grid(row=1, column=1, padx=5, pady=5)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5)

        return self.artist_entry  # focus on artist field by default

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True
        self.track_artist = self.artist_entry.get()
        self.track_title = self.title_entry.get()
        self.track_album = self.album_entry.get()


def getTitlesYouTube(artist, track):
    yt = YTMusic()
            
    if track.endswith(".mp3") or track.endswith(".wav"):
        track = track[0:-4] 
        
    search_key = '"' + artist + '" "' + track + '"'
    
    # search types: songs, videos, albums, artists, playlists, community_playlists, featured_playlists, uploads
    search_results = yt.search(search_key, "albums")
    
    choices =[] 
    releases = []
    artist_lc = artist.lower()
    releaseTitle = None
    singleTitle = None
    for item in search_results:
        artists = ''
        for artist_row in item.get('artists', []):
            artists = artist_row['name'] + ', '
    
        if artists.lower().find(artist_lc) >= 0:
            releaseTitle = item['title']
            #key = '{} -\t {}'.format(artists, releaseTitle)
            if releaseTitle not in releases:
                choices.append(releaseTitle)
                releases.append(releaseTitle)

    if len(choices) == 0:
        logit(f"YouTube search for {track} by {artist} found {len(choices)} items")

    return choices

def getTracksYouTube(artist, track):
    yt = YTMusic()

    if track.endswith(".mp3") or track.endswith(".wav"):
        track = track[0:-4]

    track = track.strip()
    artist = artist.strip()
    search_key = '"' + artist + '" "' + track + '"'

    # search types: songs, videos, albums, artists, playlists, community_playlists, featured_playlists, uploads
    search_results = yt.search(search_key, 'songs')
    #print("YouTube search for -{}- found {} items".format(search_key, len(search_results)))

    choices =[]
    releases = []
    artist_lc = artist.lower()
    releaseTitle = None
    singleTitle = None
    for item in search_results:
        artists = ''
        for artist_row in item.get('artists', []):
            artists = artist_row['name'] + ', '

        #print("item: {}, {}".format(artists, item['title']))

        if artists.lower().find(artist_lc) >= 0:
            releaseTitle = item['title']
            #key = '{} -\t {}'.format(artists, releaseTitle)
            if releaseTitle not in releases and 'videoId' in item:
                choices.append(item)
                releases.append(releaseTitle)

    return choices

#downloader = TrackDownloader("/tmp")
#downloader.fetch_track("https://www.youtube.com/watch?v=20cuFhgPLEo", True)
#downloader.fetch_track("https://www.youtube.com/watch?v=vhgxiu8TaXk", True)
