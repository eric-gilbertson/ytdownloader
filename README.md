# Youtube Download Tool

This Python3program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a DnD aware list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded to ~/Music/ytdl. This program assumes that youtube-dl has been installed and
include in the user's $PATH.

## Setup

This tool assumes that youtube-dl has been installed and included in the user's $PATH variable.

The required Python dependencies can be installed via the following:
   - pip install -r requirements.txt

Note: You may want to create a virtual environment before intalling the requirements.


## Usage

Start the tool using: python3 ytdownloader.py. 

Then using your favorite browser search Youtube for a track. Once located copy the browser's URL into the
tool's URL text field followed by <Enter>. After a short delay the track will be downloaded
to your computer and listed in the tool's file list. From the file list the track can be 
dragged into a recording tool such as Audacity. Note that the track file will be deleted 
approximately 10 seconds after the Drag and Drop operation is completed.

