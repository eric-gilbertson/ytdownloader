from tkinter import simpledialog
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter as tk

from fcc_checker import FCCChecker


class SelectAlbumDialog(simpledialog.Dialog):
    def __init__(self, parent, artist, track, album_choices):
        # store initial values
        self.artist = artist
        self.track = track
        self.album_choices = album_choices
        self.album = ''
        self.album_choices = album_choices
        self.ok_clicked = False
        super().__init__(parent, f'Select Album')

    def body(self, master):
        self.choices_entry = tk.Text(master, borderwidth=1, relief="solid", width=80)
        self.choices_entry.bind("<Double-1>", lambda e: self._select_row(e))
        self.choices_entry.config(cursor="arrow")

        self.choice_entry = tk.Entry(master, width=60)
        self.track_info = tk.Entry(master, width=60)

        idx = 0
        albums = ''
        for title in self.album_choices:
            albums = albums + f"{idx}: {title}\n"
            idx = idx + 1

        self.choices_entry.insert("1.0", albums)
        self.track_info.insert(0, f'{self.artist} - {self.track}')

        if idx > 0:
            self.choice_entry.insert(0, '0')

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
    
        

class LiveShowDialog(simpledialog.Dialog):
    def __init__(self, parent, show_title, show_start):
        self.parent = parent
        self.show_title = show_title
        self.show_start = show_start
        self.show_title_entry = None
        self.ok_clicked = False
        super().__init__(parent, "Live Show Info")

    def body(self, master):
        info_msg = "Enter the name of your Zookeeper playlist. Note that playlist must be created in Zookeeper in order to complete this operation."

        tk.Label(master, text=info_msg, wraplength=450, justify=tk.LEFT).grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        tk.Label(master, text="Show Title:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.show_title_entry = tk.Entry(master, width=40)
        self.show_title_entry.insert(0, self.show_title)
        self.show_title_entry.grid(row=1, column=1, padx=5, pady=5)
        return self.show_title_entry  # focus on artist field by default

    def buttonbox(self):
        box = tk.Frame(self)
        self.ok_button = tk.Button(box, text="OK", width=10, command=self.ok)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        box.pack()

    def apply(self):
        # When Save is clicked
        self.parent.after(10, self.parent.playlist.check_show_playlist, self.show_title_entry.get())

class UserConfigurationDialog(simpledialog.Dialog):
    def __init__(self, parent, user_configuration):

        # store initial values
        self.configuration = user_configuration
        self.show_title_entry = None
        self.show_start_combo = None
        self.ok_clicked = False
        super().__init__(parent, "Configuration")

    def body(self, master):
        tk.Label(master, text="Show Title:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.show_title_entry = tk.Entry(master, width=40)
        self.show_title_entry.insert(0, self.configuration.show_title)
        self.show_title_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(master, text="Show Start:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.show_start_combo = ttk.Combobox(master, state="readonly", width=15)
        self.show_start_combo.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        time_values = [
            '12 am', '1 am', '2 am', '3 am', '4 am', '5 am', '6 am', '7 am', '8 am', '9 am', '10 am', '11 am',
            '12 pm', '1 pm', '2 pm', '3 pm', '4 pm', '5 pm', '6 pm', '7 pm', '8 pm', '9 pm', '10 pm', '11 pm',
        ]

        self.show_start_combo['values'] = time_values
        self.show_start_combo.set(time_values[self.configuration.show_start_time])


        return self.show_title_entry  # focus on artist field by default

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True
        self.configuration.show_title = self.show_title_entry.get()
        self.configuration.save_config()

class TrackEditDialog(simpledialog.Dialog):
    def __init__(self, parent, track):
        self.ok_clicked = False
        self.track_artist = track.artist
        self.track_title  = track.title
        self.track_album = track.album
        self.track_fcc_status = track.fcc_status
        self.track_fcc_comment = track.fcc_comment

        super().__init__(parent, "Edit Track")

    def body(self, master):
        # Create labels
        tk.Label(master, text="Artist:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Album:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="FCC:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text=self.track_fcc_comment).grid(row=4, column=1, sticky="w", padx=0, pady=0)

        # Create entry fields with initial values
        self.artist_entry = tk.Entry(master, width=40)
        self.artist_entry.insert(0, self.track_artist)

        self.title_entry = tk.Entry(master, width=40)
        self.title_entry.insert(0, self.track_title)

        self.album_entry = tk.Entry(master, width=40)
        self.album_entry.insert(0, self.track_album)

        self.fcc_status_combo = ttk.Combobox(master, state="readonly", width=20)
        self.fcc_status_combo.insert(0, self.track_fcc_status)
        self.fcc_status_combo['values'] = FCCChecker.FCC_STATUS_AR
        self.fcc_status_combo.set(self.track_fcc_status)

        # Place widgets
        self.artist_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.grid(row=1, column=1, padx=5, pady=5)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5)
        self.fcc_status_combo.grid(row=3, column=1, sticky='w', padx=5, pady=5)

        return self.artist_entry  # focus on artist field by default

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True
        self.track_artist = self.artist_entry.get()
        self.track_title = self.title_entry.get()
        self.track_album = self.album_entry.get()
        self.track_fcc_status = self.fcc_status_combo.get()


