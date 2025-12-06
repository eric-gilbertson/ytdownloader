#!/usr/bin/python3
# creates a CSV for import into Zookeeper from a VLC generated .m3u playlist.
# Steps include
#   - skip lines with #
#   - process each track line as follows
#       * URL decode line
#       * extract track info from line and exit on bad format
#       * if no release lookup via YT
#       * if multiple releases present list to user for selection
#       * add complete line to output file image
#       * write file with a _new suffix
#
import os, getopt, sys, http.client, json, glob, urllib, time, requests
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from ytmusicapi import YTMusic
from urllib import request, parse

playlist_file_name = None

# from Stack Overflow
def subPairs(pairs, s):
    def repl_func(m):
        # only one group will be present, use the corresponding match
        return next(
            repl
            for (patt, repl), group in zip(pairs, m.groups())
            if group is not None
        )
    pattern = '|'.join("({})".format(patt) for patt, _ in pairs)
    retVal = re.sub(pattern, repl_func, s)
    return retVal


def subPairs2(pairs, s):
    retVal = s
    for pair in pairs:
        retVal = re.sub(pair[0], pair[1], retVal)

    return retVal

def getTrackInfo(line):
    FIELD_SEPARATOR = '^'
    artist = track = release = None
    label = '-'
    SUB_PAIRS = ([('<li>', ''), (r'- \d -', r'\t'), (' - ', r'\t'), (r'\.mp3.*', ''), (r'\.wav.*', ''), ('_', r'\t')])
    line = Path(unquote(line)).name
    line = subPairs2(SUB_PAIRS, line)
    infoAr = line.split(FIELD_SEPARATOR)
    infoLen = len(infoAr)
    if infoLen >= 2:
        artist = infoAr[0].strip()
        track = infoAr[1].strip()

        if infoLen >= 3:
            release = infoAr[2].strip()
        if infoLen >= 4:
            label = infoAr[3].strip()

    return (artist, track, release, label)

def selectTitle(artist, track, titleAr):
    titleCnt = len(titleAr)
    if titleCnt == 0:
        return None

    print("Select release for {} - {}: ".format(artist, track))
    idx = 0
    for title in titleAr:
        print('{} - {}'.format(idx, title))
        idx = idx + 1

    diskNumStr = input('Disk: ')
    if (len(diskNumStr) == 0):
        if titleCnt == 1:
            diskNumStr = "0"
        else:
            return None
    elif (len(diskNumStr) > 2):
            return diskNumStr # assume release title was entered


    diskNum = int(diskNumStr)
    if 0 <= diskNum < len(titleAr):
        title = titleAr[diskNum].split('\t')[1].strip()
        return title
    else:
        print("Invalid value, try again")
        return(selectTitle(titleAr))


def getTitlesYouTube(artist, track):
    yt = YTMusic()

    if track.endswith(".mp3") or track.endswith(".wav"):
        track = track[0:-4]

    search_key = '"' + artist + '" "' + track + '"'

    # search types: songs, videos, albums, artists, playlists, community_playlists, featured_playlists, uploads
    search_results = yt.search(search_key, "albums")
    #print("YouTube search for -{}- found {} items".format(search_key, len(search_results)))

    choices =[]
    releases = []
    artist_lc = artist.lower()
    releaseTitle = None
    singleTitle = None
    for item in search_results:
        artists = ''
        for artist_row in item.get('artists', []):
            artists = artist_row['name'] + ', '

        #print("item: {}, {}".format(artists, item['title']))

        if artists.lower().find(artist_lc) >= 0:
            releaseTitle = item['title']
            #key = '{} -\t {}'.format(artists, releaseTitle)
            if releaseTitle not in releases:
                choices.append(releaseTitle)
                releases.append(releaseTitle)

    if len(choices) == 0:
        print(f"YouTube search for {track} by {artist} found {len(choices)} items")

    return choices

def findTitleYouTube(artist, track):
    choices = getTitlesYouTube(artist, track)
    if len(choices) == 0:
        releaseTitle = input('Enter Release Title: ')
    elif len(choices):
        releaseTitle = selectTitle(artist, track, choices)


#    trackLC = track.lower()
#    if len(releases) == 0:
#        releaseTitle = input('Enter Release Title: ')
#    elif len(releases) == 1 and releases[0].lower() != trackLC:
#        releaseTitle = releases[0]
#    elif len(releases) == 2 and (releases[0].lower().find(trackLC) == 0 or releases[1].lower().find(trackLC) == 0):
#        idx = 0 if releases[1].lower().find(trackLC) == 0 else 1
#        releaseTitle = releases[idx]
#    elif len(choices):
#        releaseTitle = selectTitle(artist, track, choices)

    return releaseTitle

def get_spotify_token() -> Optional[str]:
    auth_url = 'https://accounts.spotify.com/api/token'
    response = requests.post(auth_url, { # TODO: load from external file
        'grant_type': 'client_credentials',
        'client_id': '', 
        'client_secret': ''
    })
    if response.status_code != 200:
        print("no token")
        return None

    return response.json().get('access_token')


def findTitleSpotify(artist_name: str, track_name: str) -> Optional[str]:
    album_name = ''
    token = get_spotify_token()
    if not token:
        return None

    headers = {'Authorization': f'Bearer {token}'}
    search_query = f'album:{album_name} artist:{artist_name}'
    search_type = "album"
    if len(album_name) > 0:
        search_query = f'track:{track_name} artist:{artist_name}'
        search_type = "track"

    search_url = 'https://api.spotify.com/v1/search'

    params = {
        'q': search_query,
        'type': search_type,
        'limit': 5 
    }     
         
    response = requests.get(search_url, headers=headers, params=params)
    if response.status_code != 200:
        return None 

    albums = response.json().get('albums', {}).get('items', [])
    if not albums:
        return None

    releases = []
    titles = []
    for item in albums:
        releaseTitle = item['name']
        if releaseTitle in titles:
            continue

        print(f"title: {releaseTitle}")
        key = '{} -\t {}'.format(artist_name, releaseTitle)
        releases.append(key)
        titles.append(releaseTitle)

    if len(releases) == 0:
        releaseTitle = input('Enter Release Title: ')
    else:
        releaseTitle = selectTitle(artist_name, track_name, releases)

    return releaseTitle

def findTitleDiscogs(artist, track):
    #print("Find: {} - {}".format(artist, track))
    #recording:It's five o'clock && artist:Aphrodite's Child&fmt=json&inc=
    query = 'recording:"{}" && artist:"{}"'.format(track, artist)
    url = 'https://musicbrainz.org/ws/2/recording/?limit=40&query=' + urllib.parse.quote_plus(query)
    url = 'http://musicbrainz.org/ws/2/recording/?limit=40&query=' + urllib.parse.quote_plus(query)

    req = request.Request(url, method='GET')
    req.add_header("Accept", "application/json")

    #print("url: {}".format(url))
    response = request.urlopen(req)
    #print("Status: {} and reason: {}".format(response.status, response.reason))

    if response.status != 200:
        print("Musicbrainz error: {}".format(response.status))
        return None

    result = json.loads(response.read())
    if result['count'] == 0:
        print("No results for: {} - {}".format(artist, track))

    choices = []
    releases = []
    lastReleaseTitle = None
    for recording in result['recordings']:
        artistName = recording['artist-credit'][0]['name'].lower()
        if not 'releases' in recording:
            continue

        for release in recording['releases']:
            releaseTitle = release['title']
            score = int(recording['score'])
            # protect against missing status field
            isOfficial = release.get('status', 'Official') == 'Official'
            #print("Found: {}, {}, {}, {}".format(recording['title'], artistName, releaseTitle, score))
            isNew = not releaseTitle.lower() in releases
            if isOfficial & (artist.lower().find(artistName) >= 0) & (int(score) > 90) & isNew:
                choices.append('{} -\t {}'.format(artistName, releaseTitle))
                releases.append(releaseTitle.lower())
                lastReleaseTitle = releaseTitle

    title = lastReleaseTitle
    if len(choices) > 1:
        title = selectTitle(artist, track, choices)

    return title


# return album tile for artist and track and '-' if not found.
def findTitle(artist, track):
    # get 1st artist if a comma separated list
    artist = artist.split(',')[0].strip()
    # drop anything after 'feat.'
    artist = artist.split('feat.')[0].strip()

    title = findTitleYouTube(artist, track)
    if title is None:
        title = findTitleSpotify(artist, track)

    return '-' if title is None else title

    
def parse_args(argv):
   global playlist_file_name

   try:
      opts, args = getopt.getopt(argv,"f:l:",["file","length"])
   except getopt.GetoptError:
      print (sys.argv[0] + ' -f <PLAYLIST_FILE>')
      sys.exit(2)

   for opt, arg in opts:
      if opt == '-h':
         print (sys.argv[0] + ' -f <PLAYLIST_FILE>')
         sys.exit()
      elif opt in ("-f", "--file"):
         playlist_file_name = arg;

def is_good_line(line):
    is_good = line.find('#') < 0 and line.find('vlc://pause') < 0 and line.find("LID_") < 0
    return is_good

if __name__ == '__main__':
    #global playlist_file_name

    playlist_file_name = sys.argv[1] if len(sys.argv) == 2 else None

    #parse_args(sys.argv[1:])
    if len(sys.argv) <= 1:
        print("Usage: {} <PLAYLIST_FILE or <ARTIST> <TRACK>".format(sys.argv[0]))
        sys.exit(1)
    elif len(sys.argv) == 3:
        artist = sys.argv[1]
        track = sys.argv[2]
        release = findTitle(artist, track)
        print("Search for -{}- by -{}- found: -{}-".format(track, artist, release))
        sys.exit(0)
    elif playlist_file_name is None or not os.path.exists(playlist_file_name):
        print("Error: input file -{}- does not exist.".format(playlist_file_name))
        sys.exit(1)

    playlist_file = open(playlist_file_name)
    lines = playlist_file.readlines()

    # first write out a clean version in case manual edits are needed.
#    base_filename = os.path.basename(playlist_file_name)[0:-4]
#    text_filename = base_filename + ".txt"
#    text_file = open(text_filename, 'w')
#    for line in lines:
#        if is_good_line(line):
#            line = unquote(line)
#            line = line.replace('\u2000', ' ')
#            text_file.write(os.path.basename(line))
#   text_file.close()


    result = ''
    isDirty = False
    tracks = []
    if playlist_file_name.endswith('.csv'):
        for line in lines:
            lineAr = line.split("\t")
            if len(lineAr) < 4:
                print("Invalid line: " + line)
                sys.exit(0)

            tracks.append((lineAr[0], track, release, label, file_path))
    elif playlist_file_name.endswith('.m3u'):
        for line in lines:
            if not is_good_line(line):
                continue
    
            file_path = line.strip()
            line = unquote(line)
            line = line.replace('\u2000', ' ')
            artist, track, release, label = getTrackInfo(line)
            if (artist is None) | (track is None):
                print("Invalid line: " + line)
                sys.exit(0)
            else:
                tracks.append((artist, track, release, label, file_path))
    else:
        print("Invalid input file: " + playlist_file_name)
        sys.exit(0)

    lineNum = 0
    tag = '-'
    for line in tracks:
        artist, track, release, label, file = line
        if lineNum % 8 == 0:
            result = result + "\n" # mic break

        if release is None:
            time.sleep(1) # throttle the requests
            release = findTitle(artist, track)

        newLine = f'{artist}\t{track}\t{release}\t{label}\t{tag}\t{file}\n'
        result = result + newLine
        lineNum = lineNum + 1

    new_file_name = playlist_file_name[0:-4]+ '.csv'
    print(f"New file: {new_file_name}")
    new_file = open(new_file_name, 'w')
    new_file.write(result)
    new_file.close()







    
