#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VLC like media player optimized for use in live radio features include:
- 600x600 window; top row: Stop, Save, Load, Play, Output device combobox
- Treeview: left column row number, right column filename
- Drag & drop insertion of audio files (.wav & .mp3)
- Internal drag-to-reorder rows (with blue insertion line while dragging)
- WAV + MP3 playback via pydub + pyaudio
- Countdown (time remaining) in bottom-right (no progress bar)
- Auto-play next track
- Pause-track support: add 'pause' to pause until spacebar
- Keyboard shortcuts: Space, S, Delete/Backspace, ↑/↓, Enter
- Output device selection (first entry tries to be internal speakers)
- Save/Load .m3u playlists (ignores non .wav/.mp3 lines)
"""
from m3uToPlaylist import getTitlesYouTube
import json, re, datetime
import math, os, shlex, socket, ssl, threading, traceback
import urllib.request
from urllib.parse import unquote
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk, filedialog, messagebox
import pyaudio
from pydub import AudioSegment

# ---------- Optional DnD (Finder drag/drop) ----------
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_FILES = None
    DND_AVAILABLE = False

def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    with open('/tmp/player_log.txt', 'a') as logfile:
        logfile.write(timestr + msg + '\n')

def is_stop_file(file_name):
    return file_name == 'pause' or file_name == 'break'

def is_break_file(file_name):
    return file_name == 'break'

def is_pause_file(file_name):
    return file_name == 'pause'

def HMS_from_seconds(seconds):
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    hms_str = f'{math.floor(hours):d}:{math.floor(minutes):02d}:{math.floor(secs):02d}'
    return hms_str

def seconds_from_HMS(time_hms):
    seconds = 0
    timeAr = time_hms.split(':')
    if len(timeAr) == 3:
        seconds =  int(timeAr[0])*60*60 + int(timeAr[1])*60 + int(timeAr[2])
    else:
        seconds =  int(timeAr[0])*60 + int(timeAr[1])

    return seconds


class SelectAlbumDialog(simpledialog.Dialog):
    def __init__(self, parent, artist="", track=""):
        # store initial values
        self.artist = artist
        self.track = track
        self.album = ''
        self.album_choices = []
        self.ok_clicked = False
        super().__init__(parent, f'Select Album')

    def body(self, master):

        self.choices_entry = tk.Text(master, borderwidth=1, relief="solid", width=80)
        self.choices_entry.bind("<Double-1>", lambda e: self._select_row(e))
        self.choices_entry.config(cursor="arrow")

        self.choice_entry = tk.Entry(master, width=60)
        self.track_info = tk.Entry(master, width=60)

        self.album_choices = getTitlesYouTube(self.artist, self.track)
        idx = 0
        albums = ''
        for title in self.album_choices:
            albums = albums + f"{idx}: {title}\n"
            idx = idx + 1

        self.choices_entry.insert("1.0", albums)
        self.track_info.insert(0, f'{self.artist} - {self.track}')

        if idx == 1:
            self.choice_entry.insert(0, '0')

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
            self.album = ''
        elif len(choice) == 1:
            choice_num = int(choice)
            self.album = self.album_choices[choice_num]
        else:
            self.album = choice # assume user entered track

    def _select_row(self, event):
        index = self.choices_entry.index(f"@{event.x},{event.y}")
        line_number = int(index.split('.')[0]) - 1
        if line_number >= len(self.album_choices):
            return

        self.ok_clicked = True
        self.album = self.album_choices[line_number]
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


class Track():
    def __init__(self, id, artist, title, album,  file_path, duration):
        super().__init__()
        self.id = id
        self.title = '-' if len(title) == 0 else title
        self.artist = '-' if len(artist) == 0 else artist
        self.album = '-' if len(album) == 0 else album
        self.file_path = file_path
        self.duration = duration # seconds


class Playlist():
    def __init__(self):
        super().__init__()

        self.track_idx = 0
        self.set_apikey()
        self.id = None
        self.events = None
        self.ssl_context = ssl._create_unverified_context()

    def set_apikey(self):
        #hostname = socket.gethostname()
        #ipv4_address = socket.gethostbyname(hostname)

        #key_file = 'zookeeper-local.txt'
        #if ipv4_address.startswith("171.66.118"):
        #    key_file = 'zookeeper-production.txt'

        #key_file = 'zookeeper-production.txt'
        key_file = 'zookeeper-local.txt'

        if os.path.exists(key_file):
            file = open(key_file, 'r')
            lines = file.readlines()
            for idx, line in enumerate(lines, start=0):
                if line.find('#') < 0:
                    self.API_KEY = line[0:-1]
                    self.API_URL = lines[idx+1][0:-1]
                    break
        else:
             logit("Warning: Zookeeper key file not found. " + key_file)

    
    def send_track(self, track):
        if not self.id or is_pause_file(track.title) or track.title.startswith("LID_"):
            return

        url = self.API_URL + f'/api/v2/playlist/{self.id}/events'
        method = "POST" # timestamp this track
        event_type = 'break' if is_break_file(track.title) else 'spin'
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
        req.add_header("X-APIKEY", self.API_KEY)
        response = urllib.request.urlopen(req, data=data_json.encode('utf-8'), context=self.ssl_context)
        if response.status != 200:
            logit(f"Add track error: {response.status}, {url}")
        else:
            resp_obj  = json.loads(response.read())
            logit(f"response: {resp_obj}")

    def get_show_playlist(self):
        self.id = None
        self.events = None

        url = self.API_URL + '/api/v2/playlist?filter[date]=onNow'
        req = urllib.request.Request(url, method='GET')
        response = urllib.request.urlopen(req, context=self.ssl_context)
        if response.status != 200:
            logit(f"Zookeeper not available: {url}")
            return False

        resp_obj  = json.loads(response.read())
        resp_data = resp_obj['data']
        if len(resp_data) == 0:
            logit(f"Playlist not available: {url}")
            return False

        playlist = resp_obj['data'][0]
        attrs = playlist['attributes']
        show_name = attrs['name']
        if show_name.lower() != "hanging in the boneyard":
            logit(f"Playlist not active: {show_name}")
            return False

        playlist_id = playlist['id']
        url = self.API_URL + f'/api/v2/playlist/{playlist_id}/events'
        req = urllib.request.Request(url, method='GET')
        response = urllib.request.urlopen(req, context=self.ssl_context)
        resp_obj  = json.loads(response.read())

        self.id = playlist_id
        self.events = resp_obj['data']
        return True


class AudioPlaylistApp(BaseTk):
    def __init__(self):
        super().__init__()

        self.title("Audio Playlist Player")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.geometry("600x600")
        self.minsize(480, 360)
        self.is_dirty = False

        self.app_title = ''
        self._set_title("Playlist Player")

        # ----- State -----
        self._stop_playback = threading.Event()
        self._paused = False
        self._play_thread = None
        self._track_id = None
        self._audio_total_ms = 0
        self._audio_pos_ms = 0
        self.live_show = tk.BooleanVar()
        self.playlist = Playlist()


        self._dragging_item = None          # internal reorder
        self._dragging_start_id = None          # internal reorder
        self._dragging_active = False
        self._insert_line = None            # blue insertion line widget

        self.output_devices = []            # [(index, name)]
        self._device_refresh_ms = 3000

        # ----- Layout -----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_treeview()
        #self._build_countdown()

        self._bind_shortcuts()

        # Initial output devices + auto-refresh
        self._refresh_output_devices()

    def _on_close(self):
        msg = "Quiting now will drop your recent changes. Are you sure that you want to quit?"
        if self.is_dirty and not messagebox.askokcancel("Quit", msg):
            return

        self.destroy()

    # ======================= UI BUILD =======================
    def _build_topbar(self):
        top = tk.Frame(self, height=30)
        top.grid(row=0, column=0, sticky="ew")
        self.grid_rowconfigure(0, minsize=30)

        tk.Button(top, text="Stop", command=self.stop_audio).pack(side="left", padx=(6, 6), pady=2)
        tk.Button(top, text="Save", command=self.save_playlist).pack(side="left", padx=(0, 6), pady=2)
        tk.Button(top, text="Load", command=self.load_playlist).pack(side="left", padx=(0, 12), pady=2)
        tk.Button(top, text="Play", command=self.play_selected).pack(side="left", padx=(0, 12), pady=2)
        tk.Button(top, text="Fill Albums", command=self.fill_albums).pack(side="left", padx=(0, 12), pady=2)
        tk.Button(top, text="MP3", command=self.save_mp3).pack(side="left", padx=(0, 6), pady=2)

        tk.Checkbutton(top, text="Live", command=self.live_show_change, variable=self.live_show).pack(side="left", padx=(0, 12), pady=2)

        self.output_combo = ttk.Combobox(top, state="readonly", width=15)
        self.output_combo.pack(side="right", padx=(0, 6), pady=2)

        if not DND_AVAILABLE:
            tk.Label(top, text="(Drag&Drop disabled: pip install tkinterdnd2)", fg="#b45309").pack(side="left", padx=8)

    def _build_treeview(self):
        wrap = ttk.Frame(self)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        # backing data for tree & map to
        self.tree_datamap = {}

        # Treeview
        self.tree = ttk.Treeview(wrap, columns=("num", "start_time", "artist", "title", "album"), show="headings", selectmode="extended")
        self.tree.heading("num", text="#")
        self.tree.heading("start_time", text="Time")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("title", text="Title")
        self.tree.heading("album", text="album")

        self.tree.tag_configure("pause", background="red")
        self.tree.tag_configure("break", background="yellow")

        self.tree.column("num", width=25, anchor="center", stretch=False)
        self.tree.column("start_time", width=60, anchor="center", stretch=False)
        self.tree.column("artist", width=120, anchor="w", stretch=False)
        self.tree.column("title", anchor="w", stretch=True)
        self.tree.column("album", width=120, anchor="w", stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        # Insertion line (a tiny frame placed over the Treeview)
        self._insert_line = tk.Frame(self.tree, height=2, bg="blue", highlightthickness=0)
        self._hide_insert_line()

        # Internal reorder bindings - ejg
        self.tree.bind("<Double-1>", lambda e: self._toggle_play_pause())
        self.tree.bind("<ButtonPress-1>", self._tv_on_btn1_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_drag_motion_internal, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_drop_internal, add="+")
        self.tree.bind("<Leave>", lambda e: self._hide_insert_line(), add="+")


        self.tree.bind("<Shift-Up>", lambda e: self.on_shift_arrow(e, "up"))
        self.tree.bind("<Shift-Down>", lambda e: self.on_shift_arrow(e, "down"))

        # External Finder drag/drop (only if tkinterdnd2 available)
        if DND_AVAILABLE and DND_FILES is not None:
            try:
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<DragEnter>>", lambda e: None)
                self.tree.dnd_bind("<<DragLeave>>", lambda e: self._hide_insert_line())
                self.tree.dnd_bind("<<DragMotion>>", self._on_drag_motion_external)
                self.tree.dnd_bind("<<Drop>>", self._on_external_drop)
            except Exception:
                pass  # ignore if registration fails silently

    def _build_countdown(self):
        self.countdown_label = tk.Label(self, text="00:00", anchor="e", font=("Arial", 14))
        self.countdown_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    def _bind_shortcuts(self):
        self.bind("<space>", lambda e: self._toggle_play_pause())
        self.bind("<s>", lambda e: self.stop_audio())
        self.bind("<Delete>", lambda e: self._delete_selected())
        self.bind("<BackSpace>", lambda e: self._delete_selected())
#        self.bind("<Up>", lambda e: self._move_selection(-1))
#        self.bind("<Down>", lambda e: self._move_selection(1))
        self.bind("<Return>", lambda e: self.play_selected())
        self.bind("<Control-c>", lambda e: self.copy_selected_rows())
        self.bind("<Command-c>", lambda e: self.copy_selected_rows())


    # ======================= OUTPUT DEVICES =======================
    def _list_output_devices(self):
        if pyaudio is None:
            return []
        pa = pyaudio.PyAudio()
        out = []
        try:
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxOutputChannels", 0) > 0:
                    out.append((i, info.get("name", f"Device {i}")))
        finally:
            pa.terminate()

        # Try to promote internal/built-in to first entry
        def is_internal(name: str) -> bool:
            n = name.lower()
            return ("internal" in n) or ("built-in" in n) or ("builtin" in n)

        internal = [d for d in out if is_internal(d[1])]
        others = [d for d in out if not is_internal(d[1])]
        if internal:
            out = internal[:1] + others
        return out

    def _refresh_output_devices(self, event=None):
        devices = self._list_output_devices()
        if devices != self.output_devices:
            old = self.output_combo.get()
            self.output_devices = devices
            self.output_combo["values"] = [name for _, name in devices]
            if old and old in self.output_combo["values"]:
                self.output_combo.set(old)
            elif devices:
                self.output_combo.current(0)
            else:
                self.output_combo.set("")

    def _get_selected_device_index(self):
        idx = self.output_combo.current()
        if 0 <= idx < len(self.output_devices):
            return self.output_devices[idx][0]
        return None

    # ======================= TREEVIEW HELPERS =======================
    def edit_track(self, track):
        #self.withdraw()  # Hide main window
    
        self.tree.selection_clear()

        # Pass initial values here
        artist = track.artist
        title = track.title
        album = track.album
        dialog = TrackEditDialog(self, "Edit Track",
                            artist,
                            title,
                            album)
    
        if dialog.ok_clicked:
            self.is_dirty = True
            track.artist = dialog.track_artist
            track.title = dialog.track_title
            track.album = dialog.track_album
            row_values = self.tree.item(track.id)["values"]
            row_values = (*row_values[0:2], track.artist, track.title, track.album)
            self.tree.item(track.id, values=row_values)
        else:
            logit("Canceled or no input provided.")
    
        #self.deiconify()  # restore main window

    def on_shift_arrow(self, event, direction):
        selection = self.tree.selection()
        items = self.tree.get_children("")

        if not selection:
            # if nothing selected, start at first/last
            idx = 0 if direction == "down" else len(items) - 1
        else:
            # last focused item index
            focus = self.tree.focus() or selection[-1]
            try:
                idx = items.index(focus)
            except ValueError:
                idx = 0

            idx = max(0, min(len(items) - 1, idx + (1 if direction == "down" else -1)))

        new_item = items[idx]

        # Add new item to selection
        self.tree.selection_add(new_item)
        self.tree.focus(new_item)
        self.tree.see(new_item)
        return "break"  # prevent default move


    def _renumber_rows(self):
        start_time_secs = 0
        for i, item_id in enumerate(self.tree.get_children(""), start=1):
            track = self.tree_datamap[item_id]
            start_time_HMS = HMS_from_seconds(start_time_secs)
            self.tree.item(item_id, values=(i, start_time_HMS, track.artist, track.title, track.album))
            start_time_secs = start_time_secs + track.duration

    def _delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
            self.tree_datamap.pop(item, None)
        self._renumber_rows()

    def _move_selection(self, direction: int):
        items = self.tree.get_children("")
        if not items:
            return
        sel = self.tree.selection()
        if not sel:
            self.tree.selection_set(items[0])
            self.tree.focus(items[0])
            return
        idx = items.index(sel[0])
        new = max(0, min(len(items) - 1, idx + direction))
        self.tree.selection_set(items[new])
        self.tree.focus(items[new])
        self.tree.see(items[new])

    # ----- Insertion line helpers -----
    def _show_insert_line_at_row_top(self, row_id):
        bbox = self.tree.bbox(row_id)
        if bbox:
            y = bbox[1]
            self._insert_line.place(x=0, y=y, relwidth=1)
            #self._insert_line.lift(self.tree)



    def _show_insert_line_at_end(self):
        children = self.tree.get_children("")
        if children:
            last = children[-1]
            x, y, w, h = self.tree.bbox(last)
            y_line = y + h
        else:
            # Empty list: draw near top padding
            y_line = 2
        self._insert_line.place(x=0, y=y_line, relwidth=1)
        #self._insert_line.lift(self.tree)

    def _hide_insert_line(self):
        try:
            self._insert_line.place_forget()
        except Exception:
            pass


    # ======================= INTERNAL REORDER DnD =======================
    def _tv_on_btn1_press(self, event):
        self._dragging_item = None
        row_id = self.tree.identify_row(event.y)
        if (event.state & 0x0001) != 0:
            track = self.tree_datamap[row_id]
            self.edit_track(track)
            return "break"
        elif row_id:
            self._dragging_item = row_id
            self._dragging_active = False
            self.tree.focus(row_id)

            rows = list(self.tree.get_children(""))
            self._dragging_start_idx = rows.index(row_id) if row_id else len(rows)

    def _on_drag_motion_internal(self, event):
        if not self._dragging_item:
            return

        self._dragging_active = True
        row = self.tree.identify_row(event.y)
        if row:
            self._show_insert_line_at_row_top(row)
        else:
            # if not over a row, show line at end (below last)
            self._show_insert_line_at_end()

    def _on_drop_internal(self, event):
        if not self._dragging_item or not self._dragging_active:
            self._hide_insert_line()
            return


        # Compute target by current mouse Y
        self.is_dirty = True
        dragging = self._dragging_item
        self._dragging_item = None

        row = self.tree.identify_row(event.y)
        rows = list(self.tree.get_children(""))
        drop_index = rows.index(row)  if row else len(rows)
        drag_down = drop_index > self._dragging_start_idx

        if drag_down:
            start = self._dragging_start_idx + 1
            end = drop_index - 1
            for i in range(start, end):
                row = rows[i]
                self.tree.move(row, "", i - 1)

            drop_index = drop_index - 1
        else: # drag up
            start = drop_index
            end = self._dragging_start_idx
            for i in range(start, end):
                row = rows[i]
                self.tree.move(row, "", i + 1)

        self.tree.move(dragging, "", drop_index)
        self._hide_insert_line()
        self._renumber_rows()

    # ======================= EXTERNAL DROP (Finder) =======================
    def _on_drag_motion_external(self, event):
        """While dragging from Finder, show insertion line."""
        # Some DnD events may not have reliable local y; fallback to pointer math
        if hasattr(event, "y"):
            y_local = event.y
        else:
            y_local = self.tree.winfo_pointery() - self.tree.winfo_rooty()

        row = self.tree.identify_row(y_local)
        if row:
            self._show_insert_line_at_row_top(row)
        else:
            self._show_insert_line_at_end()

    def _on_external_drop(self, event):
        data = event.data or ""
        try:
            files = self._split_dnd_paths(data)
        except Exception:
            files = [data]

        # Determine drop index from pointer position (most robust)
        self.is_dirty = True
        y_local = self.tree.winfo_pointery() - self.tree.winfo_rooty()
        target_row = self.tree.identify_row(y_local)
        siblings = list(self.tree.get_children(""))
        if target_row:
            insert_index = siblings.index(target_row) - 1
        else:
            insert_index = len(siblings)

        for path in files:
            path = path.strip()
            if not path or not path.lower().endswith((".mp3", ".wav")) or not os.path.isfile(path):
                continue

            artist = ''
            title = os.path.basename(path[0:-4])
            titleAr = title.split('^')
            if len(titleAr) > 1:
                artist = titleAr[0].strip()
                title = titleAr[1].strip()

            duration = 0 if is_stop_file(title) else len(AudioSegment.from_file(path))/1000
            tags = ()
            if is_break_file(title):
                tags = ("break")
            elif is_pause_file(title):
                tags = ("pause")

            id = self.tree.insert("", insert_index, values=(insert_index+1, "-1", artist, title, ""), tags=tags)
            track = Track(id, artist, title, '', path, duration)
            self.tree_datamap[id] = track
            insert_index += 1  # subsequent files go after

        self._renumber_rows()
        self._hide_insert_line()

    @staticmethod
    def _split_dnd_paths(data: str):
        """
        Robustly split paths coming from tkinterdnd2. Handles {braced paths with spaces}.
        """
        buf = []
        i = 0
        while i < len(data):
            if data[i] == "{":
                j = i + 1
                depth = 1
                while j < len(data) and depth:
                    if data[j] == "{":
                        depth += 1
                    elif data[j] == "}":
                        depth -= 1
                    j += 1
                content = data[i + 1:j - 1]
                buf.append(f"\"{content}\"")
                i = j
            else:
                buf.append(data[i])
                i += 1
        normalized = "".join(buf)
        return shlex.split(normalized)

    @staticmethod
    def _is_spot_file(file_name):
        is_spot = file_name.startswith("LID_") or file_name.startswith('PSA_') or file_name.startswith("PROMO_")
        return is_spot

    @staticmethod
    def _is_break_file(file_name):
        is_break = re.match('audio[0-9]+\.', file_name)
        return is_break

    # ======================= PLAYLIST SAVE/LOAD =======================
    def save_mp3(self):
        if not self.tree.get_children(""):
            logit("[Save] No files to save.")
            return

        fp = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3", "*.mp3")],
            title="Save Audio As"
        )
        if not fp:
            return

        full_show = AudioSegment.empty()
        for item in self.tree.get_children(""):
            track = self.tree_datamap[item]
            if track.file_path.endswith('.mp3'):
                audio = AudioSegment.from_mp3(track.file_path)
            elif track.file_path.endswith('.wav'):
                audio = AudioSegment.from_wav(track.file_path)
            else:
                logit("Skip: " + track.file_path)

            full_show = full_show + audio

        full_show.export(fp, format="mp3")

            
    def save_playlist(self):
        START_HOURS=14

        if not self.tree.get_children(""):
            logit("[Save] No files to save.")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Save Playlist As"
        )
        if not fp:
            return

        try:
            zk_tag = zk_label  = '-'
            zk_filename = f'{fp[0:-4]}_zk.csv'
            zk_file = open(zk_filename, "w", encoding="utf-8")
 
            time_secs = START_HOURS*60*60 # 2pm in seconds
            with open(fp, "w", encoding="utf-8") as f:
                include_timestamps = False
                for item in self.tree.get_children(""):
                    t = self.tree_datamap[item]
                    file_name = os.path.basename(t.file_path).lower()
                    if self._is_break_file(file_name):
                        include_timestamps = True
                        break
             
                    
                zk_track_start = '\n' 
                for item in self.tree.get_children(""):
                    t = self.tree_datamap[item]
                    file_name = os.path.basename(t.file_path)
                    track_start = HMS_from_seconds(time_secs)
                    line = f"{t.artist}\t{t.title}\t{t.album}\t{t.file_path}\n"
                    f.write(line)

                    if include_timestamps:
                        zk_track_start = '\t{track_start}\n'

                    if self._is_break_file(file_name):
                        # zookeeper needs all blanks for a break
                        zk_line = f"\t\t\t\t\t{zk_track_start}"
                    else:
                        zk_line = f"{t.artist}\t{t.title}\t{t.album}\t{zk_label}\t{zk_tag}\t{zk_track_start}"

                    if not self._is_spot_file(file_name):
                        zk_file.write(zk_line)

                    time_secs = time_secs + t.duration

            zk_file.close()

            fp = fp.replace(".csv", ".m3u")
            with open(fp, "w", encoding="utf-8") as f:
                for item in self.tree.get_children(""):
                    t = self.tree_datamap[item]
                    f.write(f"{t.file_path}\n")

            self.is_dirty = False
        except Exception as e:
            logit(f"[Save] Error: {e}")
            traceback.logit_exc()

    def load_playlist(self, fp=False):
        if not fp:
            fp = filedialog.askopenfilename(filetypes=[("M3U Playlist", "*.m3u"), ('CSV Playlist', "*.csv")], title="Load Playlist")
        if not fp:
            return

        children = self.tree.get_children() # used self.tree instead
        for item in children: # used self.tree instead
            self.tree.delete(item)
            self.tree_datamap = {}

        if fp.endswith("m3u"):
            self.import_m3u(fp)
        else:
            self.import_csv(fp)

    # imports files using Zookeeper form:
    # artist  track  album  tag   label  timestamp	file
    def import_csv(self, fp):
        FILE_IDX = 3
        total_secs = 0
        idx = 1

        if not os.path.exists(fp):
            logit(f'File does not exist {fp}')
            return

        with open(fp, "r", encoding="utf-8") as f:
            idx = 1
            for line in f:
                lineAr = line.strip().split('\t')
                if len(lineAr) < 4 or not os.path.exists(lineAr[FILE_IDX]):
                    logit(f"skipping: {len(lineAr)}, {line}")
                    continue

                artist = lineAr[0]
                title = lineAr[1]
                album = lineAr[2]
                file = lineAr[FILE_IDX]

                file_name = os.path.basename(file)
                seconds = 0 if is_stop_file(file_name) else len(AudioSegment.from_file(file))//1000
                track_start = HMS_from_seconds(total_secs)
                track_duration = HMS_from_seconds(seconds)
                track = Track(-1, artist, title, album, file, seconds)
                id = self.tree.insert("", "end", values=(idx, track_start, track.artist, track.title, track.album))
                track.id = id
                self.tree_datamap[id] = track
                total_secs = total_secs + seconds
                idx = idx + 1


    def import_m3u(self, fp):
        try:
            infoAr = []
            total_secs = 0
            idx = 1
            with open(fp, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if line.startswith("#EXTINF:"):
                        infoAr =  line.split(":")[1].split(',')
                    elif line.endswith((".mp3", ".wav")):
                        if line.startswith("file:///"):
                            line = unquote(line[7:])

                        if os.path.exists(line):
                            artist = ''
                            title = os.path.basename(line)
                            titleAr = title.split('^')
                            if len(titleAr) > 1:
                                artist = titleAr[0]
                                title = titleAr[1]

                            seconds = 0 if is_stop_file(title) else len(AudioSegment.from_file(line))/1000
                            track_start = HMS_from_seconds(total_secs)
                            track_duration = HMS_from_seconds(seconds)
                            self.tree.insert("", "end", values=(idx, track_start, artist, title, ""))
                            infoAr = []
                            total_secs = total_secs + seconds

        except Exception as e:
            logit(f"[Load] Error: {e}")

    # ======================= PLAYBACK =======================
    def _toggle_play_pause(self):
        # If paused due to a pause-track, space resumes to next track.
        if self._paused:
            logit("play from pause")
            self._paused = False
            self._play_next_track()
            return

        # Otherwise: if playing -> stop (acts like pause); if stopped -> play selection
        if self._play_thread and self._play_thread.is_alive() and not self._stop_playback.is_set():
            self._stop_playback.set()
        else:
            self.play_selected()

    def live_show_change(self):
        if self.live_show.get():
            self.playlist.set_apikey()
            if not self.playlist.get_show_playlist():
                tk.messagebox.showwarning(title="Error", message='Live playlist not found.')
                self.live_show.set(False)
                self.playlist.id = None
        else:
            self.playlist.id = None


    def copy_selected_rows(self):
        selected_items = self.tree.selection()  # Get IDs of selected rows
        if not selected_items:
            return  # No rows selected
    
        clipboard_content = []
        for item_id in selected_items:
            track = self.tree_datamap[item_id]
            row_data = [track.artist, track.title, track.album]
            clipboard_content.append("\t".join(map(str, row_data))) # Join columns with tabs
    
        final_clipboard_string = "\n".join(clipboard_content) # Join rows with newlines
    
        self.clipboard_clear()  # Clear existing clipboard content
        self.clipboard_append(final_clipboard_string) # Add new content
    

    def fill_albums(self):
        items = self.tree.get_children("")
        for item in items:
            track = self.tree_datamap[item]
            if len(track.album) > 1 or self._is_spot_file(track.title):
                continue

            dialog = SelectAlbumDialog(self,  artist=track.artist, track=track.title)
            if dialog.ok_clicked:
                track.album = dialog.album
                row_values = self.tree.item(track.id)["values"]
                row_values = (*row_values[0:2], track.artist, track.title, track.album)
                self.tree.item(track.id, values=row_values)
            else:
                break


    def play_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self._play_index(idx)

    def _play_index(self, index: int):
        items = self.tree.get_children("")
        if index < 0 or index >= len(items):
            return

        id = items[index]
        track = self.tree_datamap.get(id, None)
        if not track:
            logit(f"Item not found: {id}")
            return

        self._track_id = id
        self._set_title(f"{index+1}: {track.artist} - {track.title}")

        if is_stop_file(track.title):
            self._paused = True
            self._set_countdown("")
            if is_break_file(track.title):
                self.playlist.send_track(track)

            return

        self._paused = False

        # Stop current playback if any
        self.stop_audio()

        audio = AudioSegment.from_file(track.file_path)
        self._audio_total_ms = len(audio)
        self._audio_pos_ms = 0
        self._stop_playback.clear()

        # Start audio thread
        self._play_thread = threading.Thread(target=self._stream_audio_thread, args=(audio,), daemon=True)
        self._play_thread.start()

        # Start countdown UI updates
        self._start_countdown_updates()

        self.playlist.send_track(track)

    def _stream_audio_thread(self, audio_segment):
        """Audio thread: writes chunks to PyAudio; updates _audio_pos_ms."""
        pa = pyaudio.PyAudio()
        try:
            kwargs = dict(
                format=pa.get_format_from_width(audio_segment.sample_width),
                channels=audio_segment.channels,
                rate=audio_segment.frame_rate,
                output=True,
            )
            dev_index = self._get_selected_device_index()
            if dev_index is not None:
                kwargs["output_device_index"] = dev_index

            stream = pa.open(**kwargs)

            chunk_ms = 50  # smooth, low-latency
            pos = 0
            total = len(audio_segment)
            while pos < total and not self._stop_playback.is_set():
                nxt = min(pos + chunk_ms, total)
                chunk = audio_segment[pos:nxt]
                stream.write(chunk.raw_data)
                pos = nxt
                self._audio_pos_ms = pos

            stream.stop_stream()
            stream.close()
        except Exception as ex:
            logit("[Playback error]", ex)
        finally:
            try:
                pa.terminate()
            except Exception:
                pass

            # Natural end -> play next (unless stopped)
            if not self._stop_playback.is_set():
                self.after(120, self._play_next_track)
            else:
                self._audio_pos_ms = 0
                self.after(0, lambda: self._set_countdown(""))

    def stop_audio(self):
        if self._play_thread and self._play_thread.is_alive():
            self._stop_playback.set()
            self._play_thread.join(timeout=0.3)
        self._play_thread = None
        self._stop_playback.clear()
        self._audio_pos_ms = 0
        self._set_countdown("")
        self._refresh_output_devices() # pick up any new devices

    def _play_next_track(self):
        items = self.tree.get_children("")

        idx = items.index(self._track_id)
        if idx < len(items) - 1:
            next_item = items[idx + 1]
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
            self._play_index(idx + 1)

    def _set_title(self, title_str):
        self.app_title = title_str
        self.title(self.app_title)

    # ----- Countdown updates -----
    def _set_countdown(self, time_str):
        if time_str == '':
            self.app_title = "Playlist Player"

        self.title(f"{self.app_title} {time_str}")

    def  _start_countdown_updates(self):
        self._update_countdown()

    def _update_countdown(self):
        if self._audio_total_ms:
            remaining = max(self._audio_total_ms - self._audio_pos_ms, 0)
            m = int(remaining // 60000)
            s = int((remaining % 60000) // 1000)
            self._set_countdown(f"{m:02}:{s:02}")
        else:
            self._set_countdown("")

        if self._play_thread and self._play_thread.is_alive() and not self._stop_playback.is_set():
            self.after(200, self._update_countdown)
        else:
            if self._stop_playback.is_set():
                self._set_countdown("")


if __name__ == "__main__":
    app = AudioPlaylistApp()
    app.load_playlist("/Users/barbara/Documents/boneyard.csv")
    app.mainloop()

