# Youtube Download Tool

This Python3 program uses youtube-dl to download audio tracks to the local disk and displays
the downloaded files in a drag-and-drop enabled list control for easy transfer to other tools such
as Audacity. In order to conserve disk space files are deleted several seconds after they
are dragged, e.g. it assumes that the target tool creates its own copy of the file. Files
are downloaded into ~/Music/ytdl. This program assumes that youtube-dl has been installed and
included in the user's $PATH.

## Requirements
   - Python 3.9+
   - yt-dlp 2025.10.22+
   - portaudio
   - ffmpeg (required if exporting program to MP3)

## Setup

This tool assumes that youtube-dl has been installed and included in the user's $PATH variable.
The steps for the entire app tool set on a Mac from a terminal are are follows:

   - ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)" - install Homebrew, takes approximately 10 minutes
   - brew install wget
   - sudo wget https://yt-dl.org/downloads/latest/youtube-dl -O /usr/local/bin/youtube-dl
   - test youtube-dl if it cannot be executed do the following:
       - sudo chown <USER_NAME> /usr/local/bin/youtube-dl
       - chmod u+x /usr/local/bin/youtube-dl

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
Macport (recommended) are as follows:

       * identify your MacOs version by opening About This Mac (from top left)
       * goto  https://www.macports.org/install.php 
       * click the link for your MacOs version - initiates installation package download
       * double click in the downloaded image and follow directions
       * enter sudo port install yt-dlp and follow directions (this takes about 1 hour to complete)

To install using Homebrew do the following:
       * open a terminal by clicking: Finder > Applications > Utilities > Terminal.
       * enter 'brew install yt-dlp (this takes about 1 hour to complete)
       
Note that occasional changes to the YouTube interface will cause your version of yt-dlp to fail. In this case try upgrading to the newest version with 'yt-dlp --update'. 

## Setup
In order to utilize all the DJTool features, you must install several open source helper utilities, including: ffmpeg, yt-dlp and portaudio. They can be installed via direct download from the sites listed below or by a package installer such as homebrew or macport (Mac), apt (Linux) or MSYS2 (Windows). With these tools you should install the following:

   - yt-dlp (can be downloaded directly from: https://github.com/yt-dlp/yt-dlp/wiki/Installation
   - ffmpeg (can be download directly from https://www.ffmpeg.org/download.html
   - portaudio (use package manager tool)

MacOs:
Best to use homebrew but you will need to use MacPorts if you have an older OS.
   - insall homebrew, aka brew
   - brew install ffmpeg

One advantage of installing yt-dlp directly from the project gitbhub repo is that from it you can upgrade to the latest version by executing 'yt-dlp -U'. This self upgrade is not possible with versions installed via a pacakage manager which may not contain the newest version.

XXXXX
remove audioioop-ltd if older python
remove configuration.py import

After installing the helper tools, install DJTool as follows:
   - check your default system Python using 'python3 --version
   - if less than Python 3.9 install newer version from https://www.python.org/downloads/macos/
   - git clone git@github.com:eric-gilbertson/djtool.git
   - cd djtool
   - python3 -m venv venv
   - source venv/bin/activate
   - python3 -m pip install --user -r requirements.txt
   - cp configuration.py.ref configuration.py and add API keys
   - test: 'python3 djtool.py'

Use the following optional steps in order to add a desktop icon for invoking DJTool from the desktop
   - unzip djtool.app.zip -d ~/Desktop
   - edit ~/Desktop/DJTool.app/Contents/document.wflow
   - under Run Shell Script edit COMMAND_STRING to point to the project directory, e.g. cd /Users/<USER_NAME>/src/djtool; ./venv/bin/python3.9 ./djtool
   - open djtool.png in Preview and copy the image
   - RC on the DJtool desktop icon and click info (info dialog will appear)
   - click on the thumbnail image in the upper/left corner and paste the new image
   - close info dialog (DJTool icon should now display)
   - test: double click in the djtool icon


TODO:
create ~/Music/ytdl if not exist
don't translate '-' that are part of file path, e.g. kzsu-archiver
