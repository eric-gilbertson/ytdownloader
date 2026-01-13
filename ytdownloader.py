'''
This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a DnD aware list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded to ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.
'''
import glob, threading, os, datetime, shutil
from os.path import expanduser
import tkinter as tk
import tkinter.messagebox
import tkinter.ttk as ttk
from tkinter import messagebox
from tkinterdnd2 import *
from audio_trimmer import trim_audio
import pyaudio, wave
from djutils import logit

from track_downloader import TrackDownloader

YTDL_DOWNLOAD_DIR = expanduser("~") + "/Music/djtool/reserve"
STAGING_DIR = YTDL_DOWNLOAD_DIR + "/../active"

# naming fixes:
# Folk Alley Sessions: Anna Egge Girls..
# Cristina Vane Getting High in Hotel Rooms

class PlayerThread(threading.Thread):
    def __init__(self, idx, filelist):
        super(PlayerThread, self).__init__()
        self.is_playing = False
        self.stop = False
        self.filelist = filelist
        self.idx = idx

    def stop_player(self):
        self.stop = True

    def run(self):
        while not self.stop and self.idx < len(self.filelist):
            filename = self.filelist[self.idx]
            self.idx = self.idx + 1
            self.is_playing = True
            with wave.open(filename, 'rb') as wf:
                # Instantiate PyAudio and initialize PortAudio system resources (1)
                p = pyaudio.PyAudio()
    
                # Open stream (2)
                stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                                channels=wf.getnchannels(),
                                rate=wf.getframerate(),
                                output=True,
                                frames_per_buffer=4096)
    
                # Play samples from the wave file (3)
                while not self.stop and len(data := wf.readframes(1024)):
                    stream.write(data)
    
                # Close stream (4)
                stream.close()
    
            # Release PortAudio system resources (5)
            p.terminate()

            self.is_playing = False

class ControlPanel(object):
    def __init__(self, root):
        self.player = None
        self.list_widget = None
        self.downloader = TrackDownloader(YTDL_DOWNLOAD_DIR)

        top_frame = tk.Frame(master=root, height=30)
        lbl = tk.Label(master=top_frame, text='URL:')
        lbl.place(x=0, y=1)
        self.urlEntry = tk.StringVar()
        self.url = tk.Entry(master=top_frame, textvariable=self.urlEntry, width=39)
        self.url.bind('<Return>', self._on_url_enter)
        self.url.place(x=30, y=0)
        button = tk.Button(master=top_frame, command= self._fetch_url_start, text="Fetch", width=5, fg="black", )
        button.place(x=398, y=4)
        button = tk.Button(master=top_frame, command= self._reload, text="Reload", width=5, fg="black", )
        button.place(x=450, y=4)
        button = tk.Button(master=top_frame, command= self._play_file, text="Play", width=5, fg="black", )
        button.place(x=500, y=4)
        button = tk.Button(master=top_frame, command= self._stop_play, text="Stop", width=5, fg="black", )
        button.place(x=550, y=4)
        top_frame.pack(fill=tk.X)


    def _on_url_enter(self, widget):
        #logit("enter: " + self.url.get())
        self._fetch_url_start()

    def set_list_widget(self, list_widget):
        self.list_widget = list_widget
        self.list_widget.tree.bind('<Double-1>', self.double_click)
        self.list_widget.tree.bind('<BackSpace>', self.delete_click)


    def _reload(self):
        self.list_widget.reload_list()

    def _play_file(self):
        list = self.list_widget.tree.get_children()
        item_name = self.list_widget.tree.focus()
        idx = self.list_widget.tree.index(item_name)
        if self.player:
            self.player.stop_player()

        try:
            self.player = PlayerThread(idx, list)
            self.player.start()
        except Exception as ioe:
            tk.messagebox.showwarning(title='Error', message=f"Could not play file {ioe}")

    def double_click(self, event):
        item = self.list_widget.tree.focus()
        self._play_file()

    def delete_click(self, event):
        if not messagebox.askyesno("Confirmation", "Are you sure you want to deleted the selected files?", parent=root):
            return

        for item in self.list_widget.tree.selection():
            if os.path.exists(item):
                os.remove(item)

        self._reload()


    def _stop_play(self):
        item_name = self.list_widget.tree.selection()
        self.player.stop_player()

    def _fetch_url_start(self, useFullName=True):
        trackurl = self.urlEntry.get()
        logit("load url: " + trackurl)
        if self.downloader.fetch_track(root, trackurl, useFullName):
            control_panel.url.config(cursor="clock")
            control_panel.url.update()
            self._fetch_url_done(1)

    def _fetch_url_done(self, dummy):
        if not self.downloader.is_done:
            root.after(500, self._fetch_url_done, 1)
        else:
            root.bell()
            if self.downloader.name_too_long:
                if tk.messagebox.showwarning(title='Error', message='Artist name too long. Click Okay to download using UNKNOWN for the artist name'):
                    self._fetch_url_start(False)
            elif self.downloader.track.track_file:
                control_panel.url.delete(0, "end")
                control_panel.url.config(cursor="")
                control_panel.url.update()

                new_track = self.downloader.track
                if len(new_track.artist) == 0 or len(new_track.title) == 0:
                    self.downloader.edit_track(root, new_track)

                file_name = os.path.basename(new_track.track_file)
                self.list_widget.tree.insert('', 'end', iid=new_track.track_file, text=file_name, values=(['x', file_name]))
            else:
                tk.messagebox.showwarning(title='Error', message=self.downloader.err_msg)


class FilePickerListbox(object):
    def __init__(self, frame):
        self.have_shift = False
        self.tree = None
        self.item_name = None
        self._setup_widgets(frame)
        self._set_file_header()

        self.tree.drag_source_register(1, DND_FILES)
        self.tree.dnd_bind('<<DragInitCmd>>', self.drag_init)
        self.tree.dnd_bind('<<DragEndCmd>>', self.drag_end)
        self.tree.bind("<<TreeviewSelect>>", self.on_item_select)
        self.tree.bind("<Button-1>", self.on_tree_click)

        self.tree.bind("<Shift-Up>", lambda e: self.on_shift_arrow(e, "up"))
        self.tree.bind("<Shift-Down>", lambda e: self.on_shift_arrow(e, "down"))

    def on_tree_click(self, event):
        """Handle clicks for checkbox toggling and row selection."""
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)

        if region == "cell" and column == "#1":
            self.move_to_staging_dir(item)
            self.tree.delete(item)
            return "break" # prevent propagation



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


    def on_shift_change(self, event):
        if event.state == 1:
            self.have_shift = True
        else:
            self.have_shift = False


    def on_item_select(self, event):
        selected_items = self.tree.selection() # Get the selected item(s)

    def _set_file_header(self):
        msg = 'Files: ({})'.format(len(self.tree.get_children()))
        self.tree.heading('File', text=msg)


    def drag_init(self, event):
        data = ()
        self.item_name = self.tree.selection()
        if self.item_name:
            stage_files = []
            for path in self.item_name:
                stage_file = self.move_to_staging_dir(path)
                stage_files.append(stage_file)

            self.tree.dragging = True
            return ((COPY, MOVE), (DND_FILES), stage_files)
        else:
            return ((), (), ()) # what to return here?

    def move_to_staging_dir(self, file_path):
        if file_path.find("/LID_") > 0:
            return file_path

        path, name = os.path.split(file_path)
        stage_file = STAGING_DIR + "/" + name
        os.rename(file_path, stage_file)
        return stage_file

    def drag_end(self, event):
        action = event.action
        # reset the "dragging" flag to enable drops again
        for item in self.item_name:
            file_path = item

            # Don't remove LID files since they are reused.
            if file_path.find("/LID_") < 0:
                if action == 'refuse_drop':
                    path, file_name = os.path.split(item)
                    #stage_file = STAGING_DIR + "/" + file_name.replace(' ', '\u2000')
                    stage_file = STAGING_DIR + "/" + file_name
                    dest_file = path + "/" + file_name
                    os.rename(stage_file, dest_file)
                else:
                    self.tree.delete(file_path)

        self.tree.dragging = False

    def _setup_widgets(self, frame):
        container = ttk.Frame(frame)
        container.pack(fill='both', expand=True)

        # create a treeview with dual scrollbars
        self.tree = ttk.Treeview(columns=('Select', 'File'), height=520, show="headings")
        self.tree.heading('Select', text='#')
        self.tree.column('Select',  width=25, anchor="center", stretch=False)

        self.tree.heading('File', text='File')
        self.tree.column("File", anchor="w", stretch=True)

        vsb = ttk.Scrollbar(orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(column=0, row=0, sticky='nsew', in_=container)
        vsb.grid(column=1, row=0, sticky='ns', in_=container)
        hsb.grid(column=0, row=1, sticky='ew', in_=container)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        #self.populate_list()

    def reload_list(self):
        self.tree.delete(*self.tree.get_children())
        self.populate_list()

    def populate_list(self):
        ytdl_path = YTDL_DOWNLOAD_DIR + "/*"

        # move any MPE downloads (format <ARTIST> - <INDEX> - <TITLE>) into the YTDL cache
        mpe_path = expanduser("~") + "/Downloads/"
        mpe_path = mpe_path + "*- [123456789] -*"
        files = glob.glob(mpe_path + ".mp3") + glob.glob(mpe_path + ".wav")
        for mpefile in files:
            trim_audio(mpefile)
            shutil.move(mpefile, YTDL_DOWNLOAD_DIR)

        prefix_len = len(ytdl_path) - 1
        prefix = ytdl_path[0:prefix_len]
        files = glob.glob(ytdl_path)

        mergeFiles = []
        for filepath in files:
            (filepath, artist, title)  = TrackDownloader.clean_filepath(filepath)
            name = filepath[prefix_len: len(filepath)]
            mergeFiles.append([name, filepath])

        mergeFiles.sort(key=lambda x: x[0])

        current_files = self.tree.get_children()
        loadedFiles = []
        idx = len(current_files)
        for fileAr in mergeFiles:
            if fileAr[1].endswith('.json') or fileAr[1] in current_files:
                continue

            name = fileAr[0]
            if not name in loadedFiles:
                loadedFiles.append(name)
                self.tree.insert('', 'end', iid=fileAr[1], text=name, values=(['x', name]))
            else:
                pass #logit("File already exists: " + name)

        self._set_file_header()



def create_app(root):
    global control_panel, listbox

    if not shutil.which('yt-dlp'):
        tk.messagebox.showwarning('Error', "yt-dlp not found. Please check your installation.")

    if not os.path.exists(YTDL_DOWNLOAD_DIR):
        os.makedirs(YTDL_DOWNLOAD_DIR)

    if not root:
        root = TkinterDnD.Tk()
        root.title("Youtube Download Tool")
        root.geometry("560x490")



    control_panel = ControlPanel(root)
    list_frame = tk.Frame(master=root, height=300)
    list_frame.pack(fill=tk.X)
    listbox = FilePickerListbox(list_frame)
    control_panel.set_list_widget(listbox)
    listbox.populate_list()
    return root

if __name__ == '__main__':
    global root
    root = create_app(None)
    root.mainloop()



