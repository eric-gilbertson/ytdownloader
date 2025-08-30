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

Optional deps (recommended):
    pip install pyaudio pydub tkinterdnd2
    brew install ffmpeg
"""
import json
import math
import os
import shlex
import socket
import threading
import urllib.request
from urllib.parse import unquote
import tkinter as tk
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


def is_stop_file(file_name):
    return file_name.startswith('pause.') or file_name.startswith('break.')

def is_break_file(file_name):
    return file_name.startswith('break.')

def is_pause_file(file_name):
    return file_name.startswith('pause.')

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

class Playlist():
    def __init__(self):
        super().__init__()

        self.track_idx = 0
        self.API_KEY = '3c9f467a01cc2c45475ea6a8cd5683a1febe03e2'
        self.API_URL = 'http://localhost:8888'
        self.id = None
        self.events = None

    def set_apikey(self):
        hostname = socket.gethostname()
        ipv4_address = socket.gethostbyname(hostname)

        key_file = 'zookeeper-local.txt'
        if ipv4_address.startswith("171.66.118"):
            key_file = 'zookeeper-production.txt'
                
        if os.path.exists(key_file):
            file = open(key_file, 'r')
            lines = file.readlines()
            for idx, line in enumerate(lines, start=0):
                if line.find('#') < 0:
                    self.API_KEY = line[0:-1]
                    self.API_URL = lines[idx+1][0:-1]
                    break
        else:
             print("Warning: Zookeeper key file not found. " + key_file)

    
    def insert_break(self, spin):
        moveto_id = spin['id']
        url = self.API_URL + f'/api/v2/playlist/{self.id}/events'
        print(f"url: {url}")
        event = {
            "type": "event",
            "attributes": {
                "type": "break",
            }
        }

        data = {"data" : event}
        data_json = json.dumps(data)
        req = urllib.request.Request(url, method=f'POST')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", self.API_KEY)
        response = urllib.request.urlopen(req, data=data_json.encode('utf-8'))
        if response.status != 200:
            print(f"Track break insert error: {response.status}, {url}")
            return
        else:
            resp_obj = json.loads(response.read())
            data = resp_obj['data']
            break_id = data['id']
            print(f"{resp_obj}")
            method = "PATCH"  # insert a break
            event = {
                "type": "event",
                "id": break_id,
                "meta": {
                    "moveTo": f"{moveto_id}"
                }
            }

            data = {"data" : event}
            data_json = json.dumps(data)
            req = urllib.request.Request(url, method='PATCH')
            req.add_header("Content-type", "application/vnd.api+json")
            req.add_header("Accept", "text/plain")
            req.add_header("X-APIKEY", self.API_KEY)
            response = urllib.request.urlopen(req, data=data_json.encode('utf-8'))
            if response.status != 204:
                print(f"track move error")
            else:
                event = {
                    "type": "event",
                    "id": break_id,
                    "attributes": {
                        "type": "break",
                        "created": "auto",
                    }
                }

                data = {"data": event}
                data_json = json.dumps(data)
                req = urllib.request.Request(url, method=f'PATCH')
                req.add_header("Content-type", "application/vnd.api+json")
                req.add_header("Accept", "text/plain")
                req.add_header("X-APIKEY", self.API_KEY)
                response = urllib.request.urlopen(req, data=data_json.encode('utf-8'))
                print(f"set time: {response}")

    def activate_track(self, title):
        if not self.id or is_pause_file(title):
            return

        title = title.lower()
        spin = self.events[self.track_idx]
        if is_break_file(title):
            self.insert_break(spin)
            return

        if spin['attributes']['track'].lower() == title:
            self.track_idx = self.track_idx + 1
        else:
            spin = None
            for i, event in enumerate(self.events, start=0):
                attrs = event['attributes']
                if 'track' in attrs and attrs['track'].lower() == title:
                    self.track_idx = i
                    spin = event
                    break

        if not spin:
            print(f"track not found: {title}")
            return

        url = self.API_URL + f'/api/v2/playlist/{self.id}/events'
        print(f"url: {url}")
        method = "PATCH" # timestamp this track
        event =  {
            "type": "event",
            "id": f"{spin['id']}",
            "attributes": {
                "created": "auto"
             }
        }

        data = {"data" : event}
        data_json = json.dumps(data)
        req = urllib.request.Request(url, method=f'{method}')
        req.add_header("Content-type", "application/vnd.api+json")
        req.add_header("Accept", "text/plain")
        req.add_header("X-APIKEY", self.API_KEY)
        response = urllib.request.urlopen(req, data=data_json.encode('utf-8'))
        if response.status != 204:
            print(f"Track stamp error: {response.status}, {url}")

    def get_show_playlist(self):
        self.id = None
        self.events = None

        url = self.API_URL + '/api/v2/playlist?filter[date]=onNow'
        print(f"url: {url}")
        req = urllib.request.Request(url, method='GET')
        response = urllib.request.urlopen(req)
        if response.status != 200:
            print(f"Zookeeper not available: {url}")
            return False

        resp_obj  = json.loads(response.read())
        resp_data = resp_obj['data']
        if len(resp_data) == 0:
            print(f"Playlist not available: {url}")
            return False

        playlist = resp_obj['data'][0]
        attrs = playlist['attributes']
        show_name = attrs['name']
        if show_name.lower() != "hanging in the boneyard":
            print(f"Playlist not active: {show_name}")
            return False

        playlist_id = playlist['id']
        url = self.API_URL + f'/api/v2/playlist/{playlist_id}/events'
        req = urllib.request.Request(url, method='GET')
        response = urllib.request.urlopen(req)
        resp_obj  = json.loads(response.read())

        self.id = playlist_id
        self.events = resp_obj['data']
        return True


class AudioPlaylistApp(BaseTk):
    def __init__(self):
        super().__init__()

        self.title("Audio Playlist Player")
        self.geometry("600x600")
        self.minsize(480, 360)

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
        self._dragging_active = False
        self._insert_line = None            # blue insertion line widget

        self.output_devices = []            # [(index, name)]
        self._device_refresh_ms = 3000

        # ----- Layout -----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_treeview()
        self._build_countdown()

        self._bind_shortcuts()

        # Initial output devices + auto-refresh
        self._refresh_output_devices()

    # ======================= UI BUILD =======================
    def _build_topbar(self):
        top = tk.Frame(self, height=30)
        top.grid(row=0, column=0, sticky="ew")
        self.grid_rowconfigure(0, minsize=30)

        tk.Button(top, text="Stop", command=self.stop_audio).pack(side="left", padx=(6, 6), pady=2)
        tk.Button(top, text="Save", command=self.save_playlist).pack(side="left", padx=(0, 6), pady=2)
        tk.Button(top, text="Load", command=self.load_playlist).pack(side="left", padx=(0, 12), pady=2)
        tk.Button(top, text="Play", command=self.play_selected).pack(side="left", padx=(0, 12), pady=2)
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

        # Treeview
        self.tree = ttk.Treeview(wrap, columns=("num", "start_time", "duration", "name"), show="headings", selectmode="extended")
        self.tree.heading("num", text="#")
        self.tree.heading("name", text="File")
        self.tree.column("num", width=50, anchor="center", stretch=False)
        self.tree.column("start_time", width=50, anchor="center", stretch=False)
        self.tree.column("duration", width=50, anchor="center", stretch=False)
        self.tree.column("name", anchor="w", stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        # Insertion line (a tiny frame placed over the Treeview)
        self._insert_line = tk.Frame(self.tree, height=2, bg="blue", highlightthickness=0)
        self._hide_insert_line()

        # Internal reorder bindings - ejg
        self.tree.bind("<ButtonPress-1>", self._tv_on_press, add="+")
        self.tree.bind("<Double-1>", self._tv_on_double_press, add="+")
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
        self.bind_all("<space>", lambda e: self._toggle_play_pause())
        self.bind_all("<s>", lambda e: self.stop_audio())
        self.bind_all("<Delete>", lambda e: self._delete_selected())
        self.bind_all("<BackSpace>", lambda e: self._delete_selected())
#        self.bind_all("<Up>", lambda e: self._move_selection(-1))
#        self.bind_all("<Down>", lambda e: self._move_selection(1))
        self.bind_all("<Return>", lambda e: self.play_selected())

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
        for i, item in enumerate(self.tree.get_children(""), start=1):
            vals = self.tree.item(item, "values")
            duration_str = vals[2]
            name = vals[3]

            duration_secs = 0
            if duration_str == '-1' and not is_stop_file(name):
                file_path = self.tree.item(item, "tags")[0]
                duration_secs = len(AudioSegment.from_file(file_path)) / 1000
            else:
                duration_secs = seconds_from_HMS(duration_str)

            start_time_HMS = HMS_from_seconds(start_time_secs)
            duration_hms = HMS_from_seconds(duration_secs)
            self.tree.item(item, values=(i, start_time_HMS, duration_hms, name))
            start_time_secs = start_time_secs + duration_secs

    def _delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
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
        self._insert_line.lift(self.tree)

    def _hide_insert_line(self):
        try:
            self._insert_line.place_forget()
        except Exception:
            pass


    # ======================= INTERNAL REORDER DnD =======================
    def _tv_on_press(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self._dragging_item = row
            self._dragging_active = False
            #self.tree.selection_set(row)
            self.tree.focus(row)
        else:
            self._dragging_item = None

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
        row = self.tree.identify_row(event.y)
        dragging = self._dragging_item
        self._dragging_item = None

        siblings = list(self.tree.get_children(""))
        if row:
            target_index = siblings.index(row)
        else:
            target_index = len(siblings)

        # Extract and reinsert at new position
        data = self.tree.item(dragging)
        tags = data.get("tags", ())
        values = data.get("values", ())

        # Remove original before computing its old index effect
        old_index = siblings.index(dragging)
        self.tree.delete(dragging)

        # Adjust target if removing an earlier item shifted indices
        if target_index > old_index:
            target_index -= 1

        self.tree.insert("", target_index, values=values, tags=tags)
        self._renumber_rows()
        self._hide_insert_line()

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
        y_local = self.tree.winfo_pointery() - self.tree.winfo_rooty()
        target_row = self.tree.identify_row(y_local)
        siblings = list(self.tree.get_children(""))
        if target_row:
            insert_index = siblings.index(target_row)
        else:
            insert_index = len(siblings)

        for path in files:
            path = path.strip()
            if not path:
                continue
            if not path.lower().endswith((".mp3", ".wav")):
                continue
            if not os.path.isfile(path):
                continue
            name = os.path.basename(path)
            self.tree.insert("", insert_index, values=(insert_index+1, "-1", "-1", name), tags=(path,))
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

    # ======================= PLAYLIST SAVE/LOAD =======================
    def save_playlist(self):
        if not self.tree.get_children(""):
            print("[Save] No files to save.")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".m3u",
            filetypes=[("M3U Playlist", "*.m3u")],
            title="Save Playlist As"
        )
        if not fp:
            return
        if not fp.lower().endswith(".m3u"):
            fp += ".m3u"
        try:
            with open(fp, "w", encoding="utf-8") as f:
                for item in self.tree.get_children(""):
                    path = self.tree.item(item, "tags")[0]
                    f.write(path + "\n")
            print(f"[Save] Playlist saved: {fp}")
        except Exception as e:
            print(f"[Save] Error: {e}")

    def load_playlist(self, fp=False):
        if not fp:
            fp = filedialog.askopenfilename(filetypes=[("M3U Playlist", "*.m3u")], title="Load Playlist")
        if not fp:
            return

        children = self.tree.get_children() # used self.tree instead
        for item in children: # used self.tree instead
            self.tree.delete(item)

        try:
            infoAr = []
            total_secs = 0
            idx = 1
            have_break = have_pause = False
            with open(fp, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if line.startswith("#EXTINF:"):
                        infoAr =  line.split(":")[1].split(',')
                    elif line.endswith((".mp3", ".wav")):
                        if line.startswith("file:///"):
                            line = unquote(line[7:])

                        if os.path.exists(line):
                            name = os.path.basename(line) if len(infoAr) == 0 else infoAr[1]
                            seconds = 0 if is_stop_file(name) else len(AudioSegment.from_file(line))/1000
                            track_start = HMS_from_seconds(total_secs)
                            track_duration = HMS_from_seconds(seconds)
                            self.tree.insert("", "end", values=(idx, track_start, track_duration, name), tags=(line,))
                            infoAr = []
                            total_secs = total_secs + seconds

   #         idx = idx + 1
   #         self.tree.insert("", "end", values=(idx, track_start, HMS_from_seconds(0), 'pause'), tags=(line,))
   #         idx = idx + 1
   #         self.tree.insert("", "end", values=(idx, track_start, HMS_from_seconds(0), 'break'), tags=(line,))
   #         self.title(HMS_from_seconds(total_secs))
   #         self._renumber_rows()

        except Exception as e:
            print(f"[Load] Error: {e}")

    # ======================= PLAYBACK =======================
    def _tv_on_double_press(self, event):
        print("enter on_double_press")
        self.play_selected()

    def _toggle_play_pause(self):
        # If paused due to a pause-track, space resumes to next track.
        if self._paused:
            print("play from pause")
            self._paused = False
            self._play_next_track()
            return

        # Otherwise: if playing -> stop (acts like pause); if stopped -> play selection
        if self._play_thread and self._play_thread.is_alive() and not self._stop_playback.is_set():
            self._stop_playback.set()
        else:
            self.play_selected()

    def live_show_change(self):
        print(f"live show change: {self.live_show.get()}")
        if self.live_show.get():
            self.playlist.set_apikey()
            if not self.playlist.get_show_playlist():
                tk.messagebox.showwarning(title="Error", message='Live playlist not found.')
                self.live_show.set(False)

        print("exit")



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
        path = self.tree.item(id, "tags")[0]
        name = os.path.basename(path).lower()
        print(f"Play file: {id}, {name}")
        self._track_id = id
        self.title(f"{name} - {id} - {index+1}")

        if is_stop_file(name):
            self._paused = True
            self.countdown_label.config(text="00:00")
            if is_break_file(name):
                self.playlist.activate_track(name)

            return

        self._paused = False

        # Stop current playback if any
        self.stop_audio()

        audio = AudioSegment.from_file(path)
        self._audio_total_ms = len(audio)
        self._audio_pos_ms = 0
        self._stop_playback.clear()

        # Start audio thread
        self._play_thread = threading.Thread(target=self._stream_audio_thread, args=(audio,), daemon=True)
        self._play_thread.start()

        # Start countdown UI updates
        print("start countdown")
        self._start_countdown_updates()

        self.playlist.activate_track(name)

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
            print("[Playback error]", ex)
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
                self.after(0, lambda: self.countdown_label.config(text="00:00"))

    def stop_audio(self):
        if self._play_thread and self._play_thread.is_alive():
            self._stop_playback.set()
            self._play_thread.join(timeout=0.3)
        self._play_thread = None
        self._stop_playback.clear()
        self._audio_pos_ms = 0
        self.countdown_label.config(text="00:00")
        self._refresh_output_devices() # pick up any new devices

    def _play_next_track(self):
        items = self.tree.get_children("")

        idx = items.index(self._track_id)
        if idx < len(items) - 1:
            next_item = items[idx + 1]
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)

            path = self.tree.item(next_item, "tags")[0]
            name = os.path.basename(path).lower()
            self._play_index(idx + 1)

    # ----- Countdown updates -----
    def _start_countdown_updates(self):
        self._update_countdown()

    def _update_countdown(self):
        if self._audio_total_ms:
            remaining = max(self._audio_total_ms - self._audio_pos_ms, 0)
            m = int(remaining // 60000)
            s = int((remaining % 60000) // 1000)
            self.countdown_label.config(text=f"{m:02}:{s:02}")
        else:
            self.countdown_label.config(text="00:00")

        if self._play_thread and self._play_thread.is_alive() and not self._stop_playback.is_set():
            self.after(200, self._update_countdown)
        else:
            if self._stop_playback.is_set():
                self.countdown_label.config(text="00:00")


if __name__ == "__main__":
    app = AudioPlaylistApp()
    app.load_playlist("/Users/barbara/Documents/test.m3u")
    app.mainloop()

