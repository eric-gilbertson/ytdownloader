# Youtube Download Tool

This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a drag-and-drop enabled list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded into ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.

## Setup

This tool assumes that youtube-dl has been installed and included in the user's $PATH variable.
The steps for the entire app tool set on a Mac from a terminal are are follows:

   - ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)" - install Homebrew, takes approximately 10 minutes
   - brew install wget
   - sudo wget https://yt-dl.org/downloads/latest/youtube-dl -O /usr/local/bin/youtube-dl
   - test youtube-dl if it cannot be executed do the following:
       - sudo chown <USER_NAME> /usr/local/bin/youtube-dl
       - chmod u+x /usr/local/bin/youtube-dl

   - cd <SOURCE_DIR>
   - git clone git@github.com:eric-gilbertson/ytdownloader.git
   - cd ytdownloader
   - python3 -m pip install --user -r requirements.txt


Note: the ytdownloader app will not run on the lastest Apple Silicon Macbook because the required tkdnd2 Python library is not available for this architecture.


## Usage

Start the tool using: python3 ytdownloader.py. 

Then using your favorite browser search Youtube for a track. Once located, copy the browser's URL into the
tool's URL text field followed by 'Enter' (or click Fetch). After a short delay the track will be downloaded
to your computer and listed in the tool's file list. From the file list the track can be 
dragged into a recording tool such as Audacity. Note that the track file will be deleted 
approximately 10 seconds after the Drag and Drop operation is completed.

Installing yt-dlp:
Yt-dlp can be installed using on Macs using either the Homebrew (aka brew)  or Macport (aka port) 
software installation tools which can then be used to install yt-dlp. The steps for doing this using
Macport are as follows:

       * identify your MacOs version by opening About This Mac (from top left)
       * goto  https://www.macports.org/install.php 
       * click the link for your MacOs version - initiates installation package download
       * double click in the downloaded image and follow directions
       * enter sudo port install yt-dlp and follow directions (this takes about 1 hour to complete)

To install using Homebrew do the following:
       * open a terminal by clicking: Finder > Applications > Utilities > Terminal.
       * enter 'brew install yt-dlp (this takes about 1 hour to complete)
       *
       

TODO:
create ~/Music/ytdl if not exist
don't translate '-' that are part of file path, e.g. kzsu-archiver
