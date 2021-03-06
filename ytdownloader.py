'''
This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a DnD aware list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded to ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.
'''
import glob, subprocess, threading, time, os
from os.path import expanduser
from distutils import spawn
import tkinter as tk
import tkinter.messagebox
import tkinter.font as tkFont
import tkinter.ttk as ttk
from tkinterdnd2 import *

DOWNLOAD_DIR = expanduser("~") + "/Music/ytdl"
YTDL_PATH = None

def execute_command(cmd):
    try:
        print("Execute: +{}+\n".format(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        p_status = p.wait()
        if p_status != 0:
            msg = "Returned +{}+, +{}+".format(output, str(err))
            print(msg)
            tk.messagebox.showwarning(title='Error', message=msg)

        return p_status == 0
    except Exception as ioe:
        print('Exception executing command: {}, {}'.format(cmd, ioe))
        return False

def delete_file_after_delay(file_name):
    time.sleep(10)  # audacity needs time to process the file
    print("delete: " + file_name)
    os.remove(file_name)

class ControlPanel(object):
    def __init__(self, frame):
        top_frame = tk.Frame(master=root, height=30)
        lbl = tk.Label(master=top_frame, text='URL:')
        lbl.place(x=0, y=1)
        self.urlEntry = tk.StringVar()
        self.url = tk.Entry(master=top_frame, textvariable=self.urlEntry, width=40)
        self.url.bind('<Return>', self._on_url_enter)
        self.url.place(x=30, y=0)
        button = tk.Button(master=top_frame, command= self._fetch_url, text="Fetch", width=5, fg="black", )
        button.place(x=400, y=0)
        button = tk.Button(master=top_frame, command= self._reload, text="Reload", width=5, fg="black", )
        button.place(x=480, y=0)
        top_frame.pack(fill=tk.X)

    def _on_url_enter(self, widget):
        print("enter: " + self.url.get())
        self._fetch_url()

    def set_list_widget(self, list_widget):
        self.list_widget = list_widget

    def _reload(self):
        self.list_widget.reload_list();

    def _fetch_url(self):
        if not YTDL_PATH:
            tk.messagebox.showwarning('Error', "youtube-dl was not found. please check your installation.")
        else:
            print("load url: " + self.urlEntry.get())
            out_file = '"{}/%(artist)s_%(title)s.%(ext)s"'.format(DOWNLOAD_DIR)
            cmd = YTDL_PATH + ' --extract-audio --audio-format wav -o {} {}'.format(out_file, self.urlEntry.get())
            if execute_command(cmd):
                listbox.populate_list()
                self.url.delete(0, "end")

class FilePickerListbox(object):

    def __init__(self, frame):
        self.table_header = ['File']
        self.tree = None
        self.item_name = None
        self.files = []
        self._setup_widgets(frame)
        self._build_tree()

        self.tree.drag_source_register(1, DND_FILES)
        self.tree.dnd_bind('<<DragInitCmd>>', self.drag_init)
        self.tree.dnd_bind('<<DragEndCmd>>', self.drag_end)
        self.tree.dnd_bind('<<DragDataGetCmd>>', self.drag_data_get)

    def drag_init(self, event):
        data = ()
        self.item_name = self.tree.selection()
        if self.item_name:
            print("doing drag: {}".format(self.item_name))
            self.tree.dragging = True
            return ((COPY), (DND_FILES), (self.item_name))
        else:
            return 'break'

    def drag_data_get(self, event):
        print("drag data get")

    def drag_end(self, event):
        # reset the "dragging" flag to enable drops again
        file_name = self.item_name[0]
        print("drag end:" + file_name)
        # Don't delte LID files since they are reused.
        if file_name.find("/LID_") < 0:
            self.tree.delete(file_name)
            threading.Thread(target=delete_file_after_delay, args=([file_name])).start()
            self.tree.dragging = False

    def drag_data_get(self, event):
        print("drag data get")

    def _setup_widgets(self, frame):
        container = ttk.Frame(frame)
        container.pack(fill='both', expand=True)

        # create a treeview with dual scrollbars
        self.tree = ttk.Treeview(columns=self.table_header, show="headings")
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
        self.prefix_len = len(path) - 1
        self.prefix = path[0:self.prefix_len]
        files = glob.glob(path)

        current_files = self.tree.get_children()
        idx = len(current_files)
        for file in files:
            if not file.endswith('.json') and not file in current_files:
                name = file[self.prefix_len : len(file)]
                self.files.append(name)
                self.tree.insert('', 'end', iid=file, text=name, values=([name]))

    def _build_tree(self):
        for col in self.table_header:
            self.tree.heading(col, text=col.title(), command=lambda c=col: sortby(self.tree, c, 0))
            # adjust the column's width to the header string
            self.tree.column(col, width=tkFont.Font().measure(col.title()))

        self.populate_list()



if __name__ == '__main__':
    root = TkinterDnD.Tk()
    root.title("Youtube Download Tool")
    root.geometry("560x280")
    control_panel = ControlPanel(root)

    YTDL_PATH = spawn.find_executable('youtube-dl')
    print("ytdl path: " + YTDL_PATH)

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    list_frame = tk.Frame(master=root)
    list_frame.pack(fill=tk.X)
    listbox = FilePickerListbox(list_frame)
    control_panel.set_list_widget(listbox)
    root.mainloop()

