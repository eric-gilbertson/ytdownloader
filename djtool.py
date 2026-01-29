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
import glob,  pathlib,  shutil,  time, os, pyaudio, json, re, datetime, yaml
import math, os, shlex, socket, ssl, threading, traceback, urllib.request
import sys
from urllib.parse import unquote
from multiprocessing.process import parent_process
from os.path import expanduser
from pydub import AudioSegment
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, PhotoImage, scrolledtext
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinter import PhotoImage

from commondefs import *
from  system_config import SystemConfig
from fcc_checker import FCCChecker, get_album_label
from djtool_dialogs import SelectAlbumDialog, LiveShowDialog, UserConfigurationDialog, TrackEditDialog
from models import Track, ZKPlaylist, UserConfiguration
from track_downloader import TrackDownloader, getTitlesYouTube
from djutils import logit, get_logfile_path


def seconds_from_HMS(time_hms):
    seconds = 0
    timeAr = time_hms.split(':')
    if len(timeAr) == 3:
        seconds =  int(timeAr[0])*60*60 + int(timeAr[1])*60 + int(timeAr[2])
    else:
        seconds =  int(timeAr[0])*60 + int(timeAr[1])

    return seconds


class AudioPlaylistApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        # ---- macOS Dock reopen handler ----
        dock_icon = PhotoImage(file='./djtool.png')
        self.iconphoto(True, dock_icon)
        self.createcommand(
            "tk::mac::ReopenApplication",
            self.on_dock_reopen
        )
          
        self.DEFAULT_TITLE = "DJ Tool"
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log_window = None

        self.geometry("600x600")
        self.minsize(480, 360)
        self.is_dirty = False
        self.playlist = ZKPlaylist(self)
        self.last_doubleclick_time = 0

        self.playlist_file = ''
        self.app_title = ''

        # ----- State -----
        self._stop_playback = threading.Event()
        self._paused = True
        self._play_thread = None
        self._track_id = None
        self._audio_total_ms = 0
        self._audio_pos_ms = 0
        self.live_show = tk.BooleanVar()
        self.downloader = TrackDownloader(self, DJT_DOWNLOAD_DIR)
        UserConfiguration.load_config()
        SystemConfig.load_config(UserConfiguration.user_apikey)

        self.bind('<FocusIn>', lambda e: self._on_focus_in())
        self.bind('<FocusOut>', lambda e: self._on_focus_out())

        self._dragging_item = None          # internal reorder
        self._dragging_start_id = None          # internal reorder
        self._dragging_active = False
        self._insert_line = None            # blue insertion line widget

        self.output_devices = []            # [(index, name)]

        # ----- Layout -----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, minsize=30)
        self.grid_rowconfigure(1, minsize=30)
        self.grid_rowconfigure(2, weight=1)

        self._build_menubar()
        self._build_topbar(0)
        self._build_urlentry(1)
        self._build_treeview(2)
        #self._build_countdown()

        self._bind_shortcuts()
        self._refresh_output_devices()
        self._set_title()

    def on_dock_reopen(self):
        """Called when Dock icon is clicked."""
        self.deiconify()
        self.lift()
        self.focus_force()


    def _on_focus_in(self):
        self.have_focus = True

    def _on_focus_out(self):
        self.have_focus = False

    def _on_close(self):
        msg = "Quiting now will drop your recent changes. Are you sure that you want to quit?"
        if self.is_dirty and not messagebox.askokcancel("Quit", msg, parent=self):
            return

        self.destroy()

    def _fetch_track(self, use_fullname=True):
        url_entry = self.urlEntry.get()
        if self.downloader.fetch_track(self, url_entry, use_fullname):
            self.url.config(cursor="clock")
            self.url.update()
            self._fetch_track_done(1)
        else:
            self.url.config(cursor="")

                
    def _fetch_track_done(self, dummy):
        if not self.downloader.is_done:
            self.after(500, self._fetch_track_done, 1)
        else:
            self.bell()
            if self.downloader.name_too_long:
                if tk.messagebox.askokcancel(title='Error', message='Artist name too long. Click Okay to download using UNKNOWN for the artist name', parent=self):
                    self.downloader.is_done = False
                    self.downloader.name_too_long = False
                    self.downloader.fetch_track(self, 'dummy-url', False)
                    self.after(500, self._fetch_track_done(1))
                else:
                    return
            elif self.downloader.track and self.downloader.track.file_path:
                self._set_dirty(True)
                self.url.delete(0, "end")
                self.url.config(cursor="")
                self.url.update()
    
                #append track to current list
                track = self.downloader.track

                # TODO: do these in background
                status, comment = FCCChecker.fcc_song_check(track.artist, track.title)
                track.fetch_label()

                self._insert_track(-1, status, comment, track.artist, track.title, track.album, track.label, track.track_file, True)
            else:
                tk.messagebox.showwarning(title='Error', message=self.downloader.err_msg, parent=self)

                
    def _edit_configuration(self):
        dialog = UserConfigurationDialog(self)
    
        if dialog.ok_clicked:
            logit("save configuration")
        else:
            logit("Canceled or no input provided.")
 

    # ======================= UI BUILD =======================
    def _build_menubar(self):
        menubar = tk.Menu(self)

        # MacOS magic to remove Python entry in the menubar. must be done in exactly
        # this order.
        dummy_header = tk.Menu(menubar, name='apple')
        menubar.add_cascade(menu=dummy_header)
        self.config(menu=menubar)
        dummy_header.destroy()

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Configure...", command=self._edit_configuration)
        filemenu.add_command(label="Load Playlist...", command=self.load_playlist)
        filemenu.add_command(label="Save Playlist...", command=self.save_playlist)
        filemenu.add_command(label="Update Playlist", accelerator = '⌘-s', command=self.update_playlist)
        filemenu.add_command(label="Import Audio...", command=self.import_audio_files)
        filemenu.add_command(label="Save MP3...", command=self.save_mp3)
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Edit Track (Shift-Click)", command=self.edit_selected_track)
        editmenu.add_command(label="Find Albums", command=self.find_albums)
        editmenu.add_command(label="Insert Pause", command=self.insert_pause)
        editmenu.add_command(label="Insert Mic-Break", command=self.insert_mic_break)
        editmenu.add_command(label="FCC Check", command=self.fcc_check)
        menubar.add_cascade(label="Edit", menu=editmenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Log File", command=self.show_log_window)
        menubar.add_cascade(label="View", menu=viewmenu)

        self.config(menu=menubar)

    def _build_topbar(self, rownum):
        top = tk.Frame(self, height=30)
        top.grid(row=rownum, column=0, sticky="ew")

        tk.Button(top, text="■", width=3, command=self.stop_audio).pack(side="left", padx=(6, 6), pady=2)
        tk.Button(top, text="▶", width=3, command=self.play_selected).pack(side="left", padx=(0, 12), pady=2)
        tk.Checkbutton(top, text="Live Show", command=self.live_show_change, variable=self.live_show).pack(side="left", padx=(0, 12), pady=2)

        self.output_combo = ttk.Combobox(top, postcommand=self._refresh_output_devices, state="readonly", width=15)
        self.output_combo.pack(side="right", padx=(0, 6), pady=2)

    # Youtube URL entry row
    def _build_urlentry(self, rownum):
        bottom = tk.Frame(self)
        bottom.grid(row=rownum, column=0, sticky="ew")
        lbl = tk.Label(bottom, text='Song:').pack(side='left')
        self.urlEntry = tk.StringVar()
        self.url = tk.Entry(bottom, textvariable=self.urlEntry, width=39)
        self.url.pack(side='left')
        self.url.bind('<Return>', self._on_url_enter)
        self.url.bind('<space>', self._on_url_space)
        button = tk.Button(bottom, command= self._fetch_track, text="Fetch", width=5, fg="black")  
        button.pack(side='left')

    def _on_url_enter(self, widget):
        logit("enter: " + self.url.get())
        self._fetch_track()

    def _on_url_space(self, event):
        event.widget.insert("insert", event.char)
        return "break"

    def _build_treeview(self, rownum):
        wrap = ttk.Frame(self)
        wrap.grid(row=rownum, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        # backing data for tree & map to
        self.tree_datamap = {}

        # Treeview
        self.tree = ttk.Treeview(wrap, columns=("num", "start_time", "artist", "title", "album", "fcc"), show="headings", selectmode="extended")
        self.tree.heading("num", text="#")
        self.tree.heading("start_time", text="Time")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("title", text="Title")
        self.tree.heading("album", text="Album/Label")
        self.tree.heading("fcc", text="FCC")

        self.tree.tag_configure("pause", background="red")
        self.tree.tag_configure("break", background="yellow")

        self.tree.column("num", width=25, anchor="center", stretch=False)
        self.tree.column("start_time", width=60, anchor="center", stretch=False)
        self.tree.column("artist", width=120, anchor="w", stretch=True)
        self.tree.column("title", anchor="w", stretch=True)
        self.tree.column("album", width=120, anchor="w", stretch=True)
        self.tree.column("fcc", width=40, anchor="w", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        # Insertion line (a tiny frame placed over the Treeview)
        self._insert_line = tk.Frame(self.tree, height=2, bg="blue", highlightthickness=0)
        self._hide_insert_line()

        # treeview bindings
        self.tree.bind("<space>", lambda e: self._toggle_play_pause())
        self.tree.bind("<Double-1>", lambda e: self.on_double_click())
        self.tree.bind("<ButtonPress-1>", self._tv_on_btn1_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_drag_motion_internal, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_drop_internal, add="+")
        self.tree.bind("<Leave>", lambda e: self._hide_insert_line(), add="+")
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<BackSpace>", lambda e: self._delete_selected())


        self.tree.bind("<Shift-Up>", lambda e: self.on_shift_arrow(e, "up"))
        self.tree.bind("<Shift-Down>", lambda e: self.on_shift_arrow(e, "down"))

        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind("<<DragEnter>>", lambda e: None)
        self.tree.dnd_bind("<<DragLeave>>", lambda e: self._hide_insert_line())
        self.tree.dnd_bind("<<DragMotion>>", self._on_drag_motion_external)
        self.tree.dnd_bind("<<Drop>>", self._on_external_drop)

    def _build_countdown(self):
        self.countdown_label = tk.Label(self, text="", anchor="e", font=("Arial", 14))
        self.countdown_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    # global bindings
    def _bind_shortcuts(self):
        self.bind_all("<Command-s>", lambda e: self.update_playlist())
#       self.bind_all("<space>", lambda e: self._toggle_play_pause())
#        self.bind("<s>", lambda e: self.stop_audio())
#        self.bind("<Delete>", lambda e: self._delete_selected())
#        self.bind("<BackSpace>", lambda e: self._delete_selected())
#        self.bind("<Up>", lambda e: self._move_selection(-1))
#        self.bind("<Down>", lambda e: self._move_selection(1))
#        self.bind("<Return>", lambda e: self.play_selected())
#        self.bind("<Control-c>", lambda e: self.copy_selected_rows())
#        self.bind("<Command-c>", lambda e: self.copy_selected_rows())


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
    def _get_selected_index(self):
        selection_index = -1
        selected_items = self.tree.selection()  # Get IDs of selected rows
        if selected_items:
            selection_index = self.tree.index(selected_items[0])
    
        return selection_index

    def insert_pause(self):
        insert_index = self._get_selected_index()
        self._insert_track(insert_index, '', '', '', Tack.PAUSE_FILE, '', '', Track.PAUSE_FILE, True)

    def insert_mic_break(self):
        insert_index = self._get_selected_index()
        self._insert_track(insert_index, '','', '', Track.MIC_BREAK_FILE, '', '', Track.MIC_BREAK_FILE, True)


    def edit_selected_track(self):
        selected_items = self.tree.selection()  # Get IDs of selected rows
        if not selected_items:
            return  # No rows selected
    
        id = selected_items[0]
        track = self.tree_datamap[id]
        self.edit_track(track)

    def edit_track(self, track):
        #self.withdraw()  # Hide main window
    
        self.tree.selection_clear()
        dialog = TrackEditDialog(self, track)
    
        if dialog.ok_clicked:
            self._set_dirty(True)
            track.artist = dialog.track_artist
            track.title = dialog.track_title
            track.album = dialog.track_album
            track.label = dialog.track_label
            track.fcc_status = dialog.track_fcc_status
            row_values = self.tree.item(track.id)["values"]
            row_values = (*row_values[0:2], track.artist, track.title, track.album_display(), track.fcc_status_glyph())
            self.tree.item(track.id, values=row_values)
        else:
            logit("Canceled or no input provided.")
    
        self.tree.focus_force() 

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
            self.tree.item(item_id, values=(i, start_time_HMS, track.artist, track.title, track.album_display(), track.fcc_status_glyph()))
            start_time_secs = start_time_secs + track.duration

    def _delete_selected(self):
        msg = "Do you want to also delete the audio files associated with the selected entries?"
        response = messagebox.askyesnocancel("Confirm Request", msg, parent=self)
        self.tree.focus_set()      # Explicitly set focus back to the main window

        if response is None:
            return
        else:
            for item_id in self.tree.selection():
                self.tree.delete(item_id)
                track = self.tree_datamap.pop(item_id, None)
                if response and os.path.exists(track.file_path):
                    os.remove(track.file_path)
  
            self._renumber_rows()
            self._set_dirty(True)

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
        new_idx = max(0, min(len(items) - 1, idx + direction))
        self.tree.selection_set(items[new_idx])
        self.tree.focus(items[new_idx])
        self.tree.see(items[new_idx])

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
        self._set_dirty(True)
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
        ROW_CORRECTION = 28
        data = event.data or ""
        try:
            files = self._split_dnd_paths(data)
        except Exception:
            files = [data]

        # Determine drop index from pointer position (most robust)
        self._set_dirty(True)
        y_local = self.tree.winfo_pointery() - self.tree.winfo_rooty()  + ROW_CORRECTION
        target_row = self.tree.identify_row(y_local)
        siblings = list(self.tree.get_children(""))
        if target_row:
            insert_index = siblings.index(target_row) - 1
        else:
            insert_index = len(siblings)

        file_count = len(files) - 1
        for path in files:
            path = path.strip()
            if not path or not path.lower().endswith((".mp3", ".wav")) or not os.path.isfile(path):
                tk.messagebox.showwarning(title="Error", message=f'Ignoring invalid file:" {path}', parent=self)
                continue

            (artist, title, album) = self._get_track_info(path)
            self._insert_track(insert_index, '', '', artist, title, album, '', path, file_count == 0)
            insert_index += 1  # subsequent files go after
            file_count = file_count - 1

        self._hide_insert_line()

    def _get_track_info(self, file_path):
        artist = ''
        album = ''
        title = os.path.basename(file_path[0:-4])
        titleAr = title.split('^')
        if len(titleAr) > 1:
            artist = titleAr[0].strip()
            title = titleAr[1].strip()

        if len(titleAr) > 2:
            album = titleAr[2].strip()

        return (artist, title, album)


    def _insert_track(self, insert_index, fcc_status, fcc_comment, artist, title, album, label, path, update_list):
        if insert_index == -1:
            insert_index = len(self.tree.get_children(""))

        track = Track(-1, fcc_status, fcc_comment, artist, title, album, label, path, 0)

        tags = ()
        if track.is_mic_break_file():
            tags = ("break")
        elif track.is_pause_file():
            tags = ("pause")

        track.id = self.tree.insert("", insert_index, values=(insert_index+1, track.duration, artist, title, track.album_display(), track.fcc_status), tags=tags)
        self.tree_datamap[track.id] = track
    
        if update_list:
            self._renumber_rows()

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
    def save_mp3(self):
        if not shutil.which("ffmpeg"):
            tk.messagebox.showwarning(title="Error", message='ffmpeg is required for this operation.', parent=self)
            return

        if not self.tree.get_children(""):
            logit("[Save] No files to save.")
            return

        seconds = 0
        for item in self.tree.get_children(""):
            track = self.tree_datamap[item]
            seconds = seconds + track.duration

        minutes = (seconds / 3600) * 10  #rough conversion is 10 minutes per hour
        msg = f'This operation will take approximately {int(minutes)} minutes. Do you with to continue?'
        doit = tk.messagebox.askokcancel(title="Start MP3 Save?", message=msg, parent= self)
        if not doit:
            return

        suggested_filename = pathlib.Path(self.playlist_file).stem if len(self.playlist_file) > 0 else ''
        filename = filedialog.asksaveasfilename(
            initialfile=suggested_filename,
            defaultextension=".mp3",
            filetypes=[("MP3", "*.mp3")],
            title="Save Audio As"
        )
        if not filename:
            return

        logit('start wav file concatenation')
        full_show = AudioSegment.empty()
        duration = 0
        for item in self.tree.get_children(""):
            track = self.tree_datamap[item]
            duration = duration + track.duration

            audio = None
            if track.file_path.endswith('.mp3') and os.path.exists(track.file_path):
                audio = AudioSegment.from_mp3(track.file_path)
            elif track.file_path.endswith('.wav') and os.path.exists(track.file_path):
                audio = AudioSegment.from_wav(track.file_path)
            else:
                skip_msg = f"Skipping missing or unsupported file: {track.file_path}"
                logit(skip_msg)

            if audio:
                full_show = full_show + audio

        logit(f"start mp3 export {filename}")
        full_show.export(filename, format="mp3")
        logit(f"done mp3 export {filename}")
        tk.messagebox.showwarning(title="MP3 File Saved", message=f'Playlist saved as {filename}', parent= self)

    def fcc_check(self):
        if SystemConfig.check_have_genius_key():
            for track in self.tree_datamap.values():
                if not track.have_fcc_status() and not track.is_stop_file() and not track.is_spot_file():
                    status, comment = FCCChecker.fcc_song_check(track.artist, track.title)
                    track.fcc_status = status
                    track.fcc_comment = comment
                    row_values = self.tree.item(track.id)["values"]
                    row_values = (*row_values[0:5], track.fcc_status_glyph())
                    self.tree.item(track.id, values=row_values)
                    self._set_dirty(True)

            
    # import audio files from a directory.
    def import_audio_files(self):
        home_dir = expanduser("~")
        dir_path = filedialog.askdirectory( title="Add wav/mp3 files from directory",
            initialdir=home_dir)

        if not dir_path:
            return

        current_files = []
        for track in self.tree_datamap.values():
            current_files.append(track.file_path)

        audio_files = glob.glob(dir_path + "/*.mp3") + glob.glob(dir_path + "/*.wav")
        new_files = False
        for idx, file_path in enumerate(audio_files):
            if not file_path in current_files:
                (artist, title, album) = self._get_track_info(file_path)
                self._insert_track(-1, '', '', artist, title, album, '', file_path, False)
                new_files = True

        if new_files:
            self._set_dirty(True)
            self._renumber_rows()

    def update_playlist(self):
        if os.path.exists(self.playlist_file):
            self.do_playlist_save(self.playlist_file)
            playlist_name = os.path.basename(self.playlist_file)
            #tk.messagebox.showwarning(title="Playlist Updated", message=f'Playlist updates saved to {playlist_name}', parent= self)
        else:
            self.save_playlist()

    def save_playlist(self):
        fp = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                title="Save Playlist As")

        if fp:
            self.do_playlist_save(fp)

    def do_playlist_save(self, fp):
        if not fp:
            return

        self.playlist_file = fp
        try:
            time_secs = 0
            include_timestamps = False
            tracks = []
            for item in self.tree.get_children(""):
                t = self.tree_datamap[item]
                tracks.append(t.to_dict())
                file_name = os.path.basename(t.file_path).lower()
                if t.is_audio_file():
                   include_timestamps = True

            # write app playlist
            with open(fp, 'w', encoding='utf-8') as json_file:
                json.dump(tracks, json_file, indent=4, ensure_ascii=False)

            # write Zookeeper playlist
            zk_tag = zk_label  = '-'
            zk_filename = f'{fp[0:-4]}_zookeeper.csv'
            zk_file = open(zk_filename, "w", encoding="utf-8")
            zk_track_start = '\n'
            for item in self.tree.get_children(""):
                t = self.tree_datamap[item]
                file_name = os.path.basename(t.file_path)
                track_start = HMS_from_seconds(time_secs)

                if include_timestamps:
                    zk_track_start = f'{track_start}\n'

                if t.is_audio_file():
                    # zookeeper needs all blanks for a break
                    zk_line = f"\t\t\t\t\t{zk_track_start}"
                else:
                    zk_line = f"{t.artist}\t{t.title}\t{t.album}\t{zk_label}\t{zk_tag}\t{zk_track_start}"

                    if not t.is_spot_file():
                        zk_file.write(zk_line)

                    time_secs = time_secs + t.duration

            zk_file.close()

            self._set_dirty(False)
        except Exception as e:
            logit(f"[Save] Error: {e}")
            traceback.print_exc()

        self._set_title()

    def show_log_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            self.log_window.focus_force()
            return

        self.log_window = tk.Toplevel(self)
        self.log_window.title("DJTool Log")
        self.log_window.geometry("600x300")
    
        text_area = scrolledtext.ScrolledText(self.log_window, wrap=tk.WORD, width=60, height=30)
        text_area.pack(expand=True, fill='both', padx=10, pady=10)
    
        log_file = get_logfile_path()
        file_content = 'File not found.'
        try:
            with open(log_file, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except Exception as e:
            logit(f"Could not read log file: {log_file}, {e}")

        text_area.insert(tk.INSERT,file_content)

        close_button = tk.Button(self.log_window, text="Close", command=self.log_window.destroy)
        close_button.pack(pady=10)


    def load_playlist(self, fp=False):
        if not fp:
            fp = filedialog.askopenfilename(filetypes=[('JSON Playlist', "*.json")], title="Load Playlist")
        if not fp:
            return

        children = self.tree.get_children() # used self.tree instead
        for item in children: # used self.tree instead
            self.tree.delete(item)
            self.tree_datamap = {}

        self.import_json(fp)
        self.playlist_file = fp
        self._set_title()

    def import_json(self, fp):
        total_secs = 0
        idx = 1

        if not os.path.exists(fp):
            logit(f'File does not exist {fp}')
            return

        start_hour = 0
        if start_hour >= 0:
            total_secs = start_hour * 60 * 60

        logit(f"Start JSON import from: {fp}")
        try:
            with open(fp, 'r') as file:
                track_objs = json.load(file)
                idx = 1
                for track_obj in track_objs:
                    track = Track.from_dict(track_obj)
                    if track:
                        track_start = HMS_from_seconds(total_secs)
                        track.id = self.tree.insert("", "end", values=(idx, track_start, track.artist, track.title, track.album, track.fcc_status_glyph()))
                        self.tree_datamap[track.id] = track
                        total_secs = total_secs + track.duration
                        idx = idx + 1
    
            logit(f"Imported {idx} tracks.")
        except Exception as e:
            msg = (f"Error processing {fp}, {e}")
            logit(msg)
            tk.messagebox.showwarning(title="File Import Error", message=msg, parent= self)


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
            if SystemConfig.check_have_user_key():
                show_title = UserConfiguration.show_title
                LiveShowDialog(self, show_title, "12 am")
            else:
                self.clear_live_show()
        else:
            pass #self.playlist.id = None

    def clear_live_show(self):
        self.live_show.set(False)

    def check_show_playlist(self, show_title):
        if not self.playlist.check_show_playlist(show_title):
            self.live_show.set(False)

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
    

    def find_albums(self):
        if SystemConfig.check_have_spotify_key():
            for item in self.tree.get_children(""):
                track = self.tree_datamap[item]
                if len(track.album) > 1 or track.is_spot_file() or track.is_stop_file():
                    continue
    
                album_choices = getTitlesYouTube(track.artist, track.title)
                if len(album_choices) == 1:
                    track.album = album_choices[0]
                else:
                    dialog = SelectAlbumDialog(self,  track.artist, track.title, album_choices)
                    if dialog.ok_clicked:
                        track.album = dialog.album
                    else:
                        break
    
                track.fetch_label()
                row_values = self.tree.item(track.id)["values"]
                row_values = (*row_values[0:2], track.artist, track.title, track.album, track.fcc_status_glyph())
                self.tree.item(track.id, values=row_values)


    def on_double_click(self):
        cur_time = time.time()
        time_delta = cur_time - self.last_doubleclick_time
        self.last_doubleclick_time = cur_time
        if time_delta < 10:
            return

        logit(f"enter on_double_click: {time_delta}")
        self._stop_playback.set()
        if self._play_thread and self._play_thread.is_alive():
            logit("stop audio1")
            self.stop_audio()
            logit("stop audio2")

        logit("play selected from double")
        self.play_selected()

    def play_selected(self):
        if not (sel := self.tree.selection()):
            return

        idx = self.tree.index(sel[0])
        logit(f"play selected: {idx}")
        self._play_index(idx)

    def _play_index(self, index: int):
        logit(f'enter _play_index {index}')
        items = self.tree.get_children("")
        if index < 0 or index >= len(items):
            return

        id = items[index]
        track = self.tree_datamap.get(id, None)
        logit(f'enter _play_index {index}, {track.title}')
        if not track:
            logit(f"Item not found: {id}")
            return

        self._track_id = id
        self._set_title(f"{index+1}: {track.artist} - {track.title}")

        if track.is_stop_file():
            self._paused = True
            self._set_countdown("")
            if track.is_mic_break_file():
                self.playlist.send_track(track)

            return

        self._paused = False

        # Stop current playback if any
        self.stop_audio()

        try:
            audio = AudioSegment.from_file(track.file_path)
        except BaseException as ex:
            logit(f"File not playable {track.file_path}, {ex}")
            self._play_next_track()
            return

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
                channels=audio_segment.channels, rate=audio_segment.frame_rate,
                frames_per_buffer=4096, output=True,
            )
            if (dev_index := self._get_selected_device_index()) is not None:
                kwargs["output_device_index"] = dev_index

            stream = pa.open(**kwargs)

            chunk_ms = 50  # smooth, low-latency
            pos = 0
            total = len(audio_segment)
            logit(f"start play: {pos}, {total}, {self._stop_playback.is_set()}")
            while pos < total and not self._stop_playback.is_set():
                nxt = min(pos + chunk_ms, total)
                chunk = audio_segment[pos:nxt]
                stream.write(chunk.raw_data)
                pos = nxt
                self._audio_pos_ms = pos

            logit(f"done playing")
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
            self._set_title("")
            if not self._stop_playback.is_set():
                logit("done, play next track")
                self.after(120, self._play_next_track)
            else:
                logit("halt playback")
                self._audio_pos_ms = 0
                self.after(0, lambda: self._set_countdown(""))

    def stop_audio(self):
        logit(f"stop_audio: enter")
        if self._play_thread and self._play_thread.is_alive():
            logit(f"stop_audio: stop_playback")
            self._stop_playback.set()
            self._play_thread.join(timeout=2.0)
            logit(f"stop_audio: stop_playback")

        self._play_thread = None
        #self._stop_playback.clear()
        self._audio_pos_ms = 0
        self._set_countdown("")

    def _play_next_track(self):
        logit(f"enter play_next_track")
        items = self.tree.get_children("")

        idx = items.index(self._track_id)
        if idx < len(items) - 1:
            next_item = items[idx + 1]
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
            self._play_index(idx + 1)

    def _set_dirty(self, is_dirty):
        self.is_dirty = is_dirty
        if not self._play_thread or not self._play_thread.is_alive():
            self._set_title()

    def _set_title(self, title_str=''):
        self.app_title = self.DEFAULT_TITLE
        if len(title_str) > 0:
            self.app_title = title_str
        elif len(self.playlist_file) > 0:
            suffix = '*' if self.is_dirty else ''
            self.app_title = f'{self.DEFAULT_TITLE} - {pathlib.Path(self.playlist_file).stem}{suffix}'

        self.title(self.app_title)

    # ----- Countdown updates -----
    def _set_countdown(self, time_str):
        self.title(f"{self.app_title} {time_str}")

    def  _start_countdown_updates(self):
        self._update_countdown()

    def _update_countdown(self):
        if self._audio_total_ms:
            remaining = max(self._audio_total_ms - self._audio_pos_ms, 0)
            m = int(remaining // 60000)
            s = int((remaining % 60000) // 1000)
            if m == 0 and s == 0:
                self._set_countdown("")
            else:
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
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        print("load playlist: " + sys.argv[1])
        app.load_playlist(sys.argv[1])

    app.mainloop()

