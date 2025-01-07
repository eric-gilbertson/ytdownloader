'''
This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a DnD aware list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded to ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.
'''
import glob, subprocess, threading, time, os, datetime, re
import urllib.parse
from os.path import expanduser
from shutil import which
from pathlib import Path
import tkinter as tk
import tkinter.messagebox
import tkinter.font as tkFont
import tkinter.ttk as ttk
from tkinterdnd2 import *
from audio_trimmer import trim_audio
import pyaudio, wave

DOWNLOAD_DIR = expanduser("~") + "/Music/ytdl"
STAGING_DIR = DOWNLOAD_DIR + "/staging"
YTDL_PATH = None


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
    new_file = filepath

    # remove parenthetical and bracketed text
    new_file = re.sub("[\(\[].*?[\)\]]", "", new_file)

    if new_file.find('｜') >= 0:
        new_file = new_file.replace('｜', '\t')

    if new_file.find('＂') >= 0:  # special fat double quote from &quot; in html
        new_file = new_file.replace('＂', '')

    if new_file.find('"') >= 0:  # regular double quote
        new_file = new_file.replace('"', '')

    if new_file.find('-') >= 0:
        new_file = new_file.replace('-', '\t')

    if new_file.find('–') >= 0:
        new_file = new_file.replace('–', '\t')

    if new_file.find('Official HD Audio') >= 0:  # regular double quote
        new_file = new_file.replace(' Official HD Audio', '')

    if new_file.find('Official Music Video') >= 0:  # regular double quote
        new_file = new_file.replace(' Official Music Video', '')

    if new_file.find('NA_') >= 0:
        new_file = new_file.replace('NA_', '')

    # just in case we lost the suffix in the transform.
    if not new_file.endswith('.wav'):
        new_file += '.wav'

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
        length = len(errmsg)

        fatalMsg = errmsg.find("HTTP Error 403 Forbidden") > 0
        ignoreMsg = ((errmsg.find('Skipping player responses from android') > 0) | \
                     (errmsg.find('You may experience throttling for some formats') > 0) | \
                     (errmsg.find('Signature extraction failed:') > 0))
        print("msg: {}, {}".format(ignoreMsg, fatalMsg))
        ignoreMsg = (ignoreMsg == True) and (fatalMsg == False)

        if errmsg.find('File name too long') > 0:
            tk.messagebox.showwarning(title='Error', message='Artist name too long. Click Okay to download using UNKNOWN for the artist name')
            control_panel._fetch_url(False)
            return

        if (command_thread.process.returncode == 0 and (fatalMsg == False) and (ignoreMsg or len(errmsg) < 4)):
            res = str(command_thread.stdout, 'utf-8')
            idx1 = res.rfind("Destination: ") + 13
            idx2 = res.find(".wav", idx1)
            if idx1 > 13 and idx2 > idx1:
                filepath =  res[idx1:idx2+4]
                filepath = clean_filepath(filepath)
                logit("Add file: " + filepath)
                trim_audio(filepath)

                listbox.populate_list()
                control_panel.url.delete(0, "end")
                control_panel.url.config(cursor="")
                #control_panel.url.config({"background": "Green"})
                control_panel.url.update()
            else:
                errmsg = res

        if len(errmsg) > 4 and not ignoreMsg:
            tk.messagebox.showwarning(title='Error', message=errmsg)
            #control_panel.url.config({"background": "Red"})
            #control_panel.url.update()


def execute_command(cmd):
    try:
        #logit("Execute: +{}+\n".format(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        p_status = p.wait()
        root.bell()
        if p_status != 0:
            msg = "Returned +{}+, +{}+".format(output, str(err))
            tk.messagebox.showwarning(title='Error', message=msg)

        return p_status == 0
    except Exception as ioe:
        logit('Exception executing command: {}, {}'.format(cmd, ioe))
        return False

def delete_file_after_delay(file_name):
    if os.path.exists(file_name):
        time.sleep(10)  # audacity needs time to process the file
        #os.remove(file_name)

class ControlPanel(object):
    def __init__(self, frame):
        self.player = None
        self.list_widget = None

        top_frame = tk.Frame(master=root, height=30)
        lbl = tk.Label(master=top_frame, text='URL:')
        lbl.place(x=0, y=1)
        self.urlEntry = tk.StringVar()
        self.url = tk.Entry(master=top_frame, textvariable=self.urlEntry, width=40)
        self.url.bind('<Return>', self._on_url_enter)
        self.url.place(x=30, y=0)
        button = tk.Button(master=top_frame, command= self._fetch_url, text="Fetch", width=5, fg="black", )
        button.place(x=370, y=0)
        button = tk.Button(master=top_frame, command= self._reload, text="Reload", width=5, fg="black", )
        button.place(x=450, y=0)
        button = tk.Button(master=top_frame, command= self._play_file, text="Play", width=5, fg="black", )
        button.place(x=530, y=0)
        button = tk.Button(master=top_frame, command= self._stop_play, text="Stop", width=5, fg="black", )
        button.place(x=610, y=0)
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
            out_file = '"{}/{}_%(title)s.%(ext)s"'.format(DOWNLOAD_DIR, artistTerm)

            cmd = YTDL_PATH + ' --extract-audio --audio-format wav -o {} {}'.format(out_file, self.urlEntry.get())
            logit("cmd: " + cmd)
            download_thread = CommandThread(cmd)
            control_panel.url.config(cursor="clock")
            control_panel.url.update()
            download_thread.start()
            schedule_check(download_thread)

class FilePickerListbox(object):

    def __init__(self, frame):
        self.table_header = ['File']
        self.tree = None
        self.item_name = None
        self._setup_widgets(frame)
        self._build_tree()
        self._set_file_header()

        self.tree.drag_source_register(1, DND_FILES)
        self.tree.dnd_bind('<<DragInitCmd>>', self.drag_init)
        self.tree.dnd_bind('<<DragEndCmd>>', self.drag_end)

    def _set_file_header(self):
        msg = 'Files: ({})'.format(len(self.tree.get_children()))
        self.tree.heading('File', text=msg)


    def drag_init(self, event):
        print("drag init")
        data = ()
        self.item_name = self.tree.selection()
        if self.item_name:
            print("doing drag: {}".format(self.item_name))
            path, name = os.path.split(self.item_name[0])
            stage_file = STAGING_DIR + "/" + name
            os.rename(self.item_name[0], stage_file)
            self.tree.dragging = True
            return ((COPY, MOVE), (DND_FILES), (urllib.parse.quote(stage_file)))
        else:
            return ((), (), ()) # what to return here?

    def drag_end(self, event):
        print("drag end")
        action = event.action
        # reset the "dragging" flag to enable drops again
        file_name = self.item_name[0]
        print("drag end: {}, {}".format(action, file_name))
        # Don't remove LID files since they are reused.
        if file_name.find("/LID_") < 0:
            self.tree.delete(file_name)
            self.tree.dragging = False


    def _setup_widgets(self, frame):
        container = ttk.Frame(frame)
        container.pack(fill='both', expand=True)

        # create a treeview with dual scrollbars
        self.tree = ttk.Treeview(columns=self.table_header, height=520, show="headings")
        vsb = ttk.Scrollbar(orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(column=0, row=0, sticky='nsew', in_=container)
        vsb.grid(column=1, row=0, sticky='ns', in_=container)
        hsb.grid(column=0, row=1, sticky='ew', in_=container)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

    def reload_list(self):
        self.tree.delete(*self.tree.get_children())
        self.populate_list()

    def populate_list(self):
        path = DOWNLOAD_DIR + "/*"
        prefix_len = len(path) - 1
        prefix = path[0:prefix_len]
        files = glob.glob(path)

        mergeFiles = []
        for file in files:
            name = file[prefix_len: len(file)]
            mergeFiles.append([name, file])

        path = expanduser("~") + "/Downloads/"
        prefix_len = len(path)
        path = path + "*- * - *.mp3"
        prefix = path[0:prefix_len]
        files = glob.glob(path)

        for file in files:
            name = file[prefix_len: len(file)]
            mergeFiles.append([name, file])

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
                self.tree.insert('', 'end', iid=fileAr[1], text=name, values=([name]))
            else:
                pass #logit("File already exists: " + name)

        self._set_file_header()


    def _build_tree(self):
        for col in self.table_header:
            self.tree.heading(col, text=col.title(), command=lambda c=col: sortby(self.tree, c, 0))
            # adjust the column's width to the header string
            self.tree.column(col, width=tkFont.Font().measure(col.title()))

        self.populate_list()

def resize(event):
    logit("height: ", event.height, "width: ", event.width)

if __name__ == '__main__':
    root = TkinterDnD.Tk()
    root.title("Youtube Download Tool")
    root.geometry("560x490")
    control_panel = ControlPanel(root)

    YTDL_PATH = which('yt-dlp')
    #YTDL_PATH = "/Users/Barbara/src/youtube-dl/youtube-dl"

    logit("ytdl path: {}".format(YTDL_PATH))

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    list_frame = tk.Frame(master=root, height=300)
    list_frame.pack(fill=tk.X)
    listbox = FilePickerListbox(list_frame)
    control_panel.set_list_widget(listbox)
    #root.bind("<Configure>", resize)
    root.mainloop()

