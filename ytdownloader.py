'''
This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a DnD aware list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded to ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.
'''
import glob, subprocess, threading, time, os, datetime, re, shutil
import urllib.parse
from os.path import expanduser
from shutil import which
from pathlib import Path
import tkinter as tk
import tkinter.messagebox
from tkinter import simpledialog
import tkinter.font as tkFont
import tkinter.ttk as ttk
from tkinterdnd2 import *
from audio_trimmer import trim_audio
import pyaudio, wave

YTDL_DOWNLOAD_DIR = expanduser("~") + "/Music/ytdl"
STAGING_DIR = YTDL_DOWNLOAD_DIR + "/staging"
YTDL_PATH = None

# naming fixes:
# Folk Alley Sessions: Anna Egge Girls..
# Cristina Vane Getting High in Hotel Rooms

def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    with open('/tmp/ytdl_log.txt', 'a') as logfile:
        logfile.write(timestr + msg + '\n')


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
                                output=True)
    
                # Play samples from the wave file (3)
                while not self.stop and len(data := wf.readframes(1024)):
                    stream.write(data)
    
                # Close stream (4)
                stream.close()
    
            # Release PortAudio system resources (5)
            p.terminate()

            self.is_playing = False

# TODO
# escape quotes in downloaded filename when invoking ffmpeg trim.
# set input box red/green upon completion
# remove '(Official Video)' and '(Lyric Video)' and single quotes from filename.
class CommandThread(threading.Thread):
    def __init__(self, cmd):
        super(CommandThread, self).__init__()
        self.cmd = cmd
        self.process = None
        self.stdout = None
        self.stderr = None

    def run(self):
        self.process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (self.stdout, self.stderr) = self.process.communicate()
        pass

def schedule_check(command_thread):
    root.after(2000, check_if_done, command_thread)


def clean_filepath(filepath):
    FIELD_SEPARATOR='^'
    new_name = os.path.basename(filepath)

    if not (filepath.endswith('.wav') or filepath.endswith(".mp3")):
        return filepath

    # remove parenthetical and bracketed text
    new_name = re.sub(r"[\(\[\{].*?[\)\]\}]", "", new_name)
    new_name = re.sub(r'- \d+ -', FIELD_SEPARATOR, new_name)

    # replace quoted song with seperator, e.g. John Craige "Judias"
#    match = re.search(r"([^'\"]*)['\"]([^'\"]*)", new_name)
#    if match and len(match.groups()) == 2:
#        new_name = f"{match.group(1)} {FIELD_SEPARATOR} {match.group(2)}"

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

    splitAr = new_name.split(FIELD_SEPARATOR)
    if len(splitAr) != 2:
        new_name  = simpledialog.askstring("File Name", "Track Name\t\t\t\t\t\t", initialvalue=f"{new_name}")
    new_file = f"{os.path.dirname(filepath)}/{new_name}"

    # trim secondary artist names, e.g. anything after a comma
    nameAr = new_file.split(FIELD_SEPARATOR)
    commaIdx = nameAr[0].find(',')
    if commaIdx > 0 and len(nameAr) > 1:
        new_file = f"{nameAr[0][0:commaIdx]} {FIELD_SEPARATOR} {nameAr[1]}"

    if new_file != filepath:
        logit("Rename: {}, {}".format(filepath, new_file))
        os.rename(filepath, new_file)

    Path(new_file).touch()
    return new_file


def check_if_done(command_thread):
    if command_thread.process.returncode == None:
        schedule_check(command_thread)
    else:
        root.bell()
        errmsg = str(command_thread.stderr) # returns '\\\' even when there is no error.
        if errmsg.find('File name too long') > 0:
            tk.messagebox.showwarning(title='Error', message='Artist name too long. Click Okay to download using UNKNOWN for the artist name')
            control_panel._fetch_url(False)
            return

        if command_thread.process.returncode == 0:
            res = str(command_thread.stdout, 'utf-8')
            idx1 = res.rfind("Destination: ") + 13
            idx2 = res.find(".wav", idx1)
            if idx1 > 13 and idx2 > idx1:
                errmsg = ''
                filepath =  res[idx1:idx2+4]
                logit("Downloaded file: " + filepath)
                filepath = clean_filepath(filepath)
                trim_audio(filepath)

                listbox.populate_list()
                control_panel.url.delete(0, "end")
                control_panel.url.config(cursor="")
                #control_panel.url.config({"background": "Green"})
                control_panel.url.update()

        if len(errmsg) > 0:
            control_panel.url.config(cursor="")
            tk.messagebox.showwarning(title='Error', message=errmsg)
            #control_panel.url.config({"background": "Red"})
            #control_panel.url.update()


def delete_file_after_delay(file_name):
    if os.path.exists(file_name):
        time.sleep(10)  # audacity needs time to process the file
        #os.remove(file_name)

class ControlPanel(object):
    def __init__(self, root):
        self.player = None
        self.list_widget = None

        top_frame = tk.Frame(master=root, height=30)
        lbl = tk.Label(master=top_frame, text='URL:')
        lbl.place(x=0, y=1)
        self.urlEntry = tk.StringVar()
        self.url = tk.Entry(master=top_frame, textvariable=self.urlEntry, width=39)
        self.url.bind('<Return>', self._on_url_enter)
        self.url.place(x=30, y=0)
        button = tk.Button(master=top_frame, command= self._fetch_url, text="Fetch", width=5, fg="black", )
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
        self._fetch_url()

    def set_list_widget(self, list_widget):
        self.list_widget = list_widget
        self.list_widget.tree.bind('<Double-1>', self.double_click)
        self.list_widget.tree.bind('<BackSpace>', self.delete_click)


    def _reload(self):
        self.list_widget.reload_list();

    def _play_file(self):
        list = self.list_widget.tree.get_children()
        item_name = self.list_widget.tree.focus()
        idx = self.list_widget.tree.index(item_name)
        print("Play: " + item_name)
        if self.player:
            self.player.stop_player()

        self.player = PlayerThread(idx, list)
        self.player.start()


    def double_click(self, event):
        item = self.list_widget.tree.focus()
        print("double: {}".format(item))
        self._play_file()
    def delete_click(self, event):
        item = self.list_widget.tree.selection()[0]
        print("delete: {}".format(item))
        if os.path.exists(item):
            os.remove(item)
        self._reload()


    def _stop_play(self):
        item_name = self.list_widget.tree.selection()
        print("stop play")
        self.player.stop_player()

    def _fetch_url(self, useFullName=True):
        #control_panel.url.config({"background": "White"})
        #control_panel.url.update()

        if not YTDL_PATH:
            tk.messagebox.showwarning('Error', "youtube-dl was not found. please check your installation.")
        else:
            artistTerm = '%(artist)s' if useFullName else 'UNKNOWN'
            logit("load url: " + self.urlEntry.get())
            out_file = '"{}/{}_%(title)s.%(ext)s"'.format(YTDL_DOWNLOAD_DIR, artistTerm)

            cmd = YTDL_PATH + ' --extract-audio --audio-format wav -o {} {}'.format(out_file, self.urlEntry.get())
            logit("cmd: " + cmd)
            download_thread = CommandThread(cmd)
            control_panel.url.config(cursor="clock")
            control_panel.url.update()
            download_thread.start()
            schedule_check(download_thread)

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

        print(f"Shift change {self.have_shift}")

    def on_item_select(self, event):
        print(f"Shift {self.have_shift}")
        selected_items = self.tree.selection() # Get the selected item(s)
        for item in selected_items:
            print("Selected item:", self.tree.item(item, "text"))

    def _set_file_header(self):
        msg = 'Files: ({})'.format(len(self.tree.get_children()))
        self.tree.heading('File', text=msg)


    def drag_init(self, event):
        print("drag init")
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
        print("drag end")
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

        self.populate_list()

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
            print("move file: " + mpefile)
            trim_audio(mpefile)
            shutil.move(mpefile, YTDL_DOWNLOAD_DIR)

        prefix_len = len(ytdl_path) - 1
        prefix = ytdl_path[0:prefix_len]
        files = glob.glob(ytdl_path)

        mergeFiles = []
        for filepath in files:
            filepath = clean_filepath(filepath)
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
                #print("add: " + name)
                self.tree.insert('', 'end', iid=fileAr[1], text=name, values=(['x', name]))
            else:
                pass #logit("File already exists: " + name)

        self._set_file_header()



def resize(event):
    logit("height: ", event.height, "width: ", event.width)

def create_app(root):
    global YTDL_PATH, control_panel, listbox

    YTDL_PATH = shutil.which('yt-dlp')
    if not os.path.exists(YTDL_DOWNLOAD_DIR):
        os.makedirs(YTDL_DOWNLOAD_DIR)

    logit("ytdl path: {}".format(YTDL_PATH))

    if not root:
        root = TkinterDnD.Tk()
        root.title("Youtube Download Tool")
        root.geometry("560x490")



    control_panel = ControlPanel(root)
    list_frame = tk.Frame(master=root, height=300)
    list_frame.pack(fill=tk.X)
    listbox = FilePickerListbox(list_frame)
    control_panel.set_list_widget(listbox)
    return root

if __name__ == '__main__':
    root = create_app(None)
    root.mainloop()

