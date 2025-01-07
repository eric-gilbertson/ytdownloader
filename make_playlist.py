#!/usr/bin/python3
# creates a CSV for import into Zookeeper from an HTML playlist generart
# via the VLC player tool. Steps include
#   - skip everything up the first <ol> tag
#   - process each <li> line as follows
#       * decode any HTML encoding
import html
# and adds it to a new output file which is identified by an '_new' file
# suffix.
#
import os, getopt, sys, http.client, json, glob, urllib, time
import re
from html.parser import HTMLParser
from pathlib import Path

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
    artist = track = release = None
    label = '-'
    SUB_PAIRS = ([('<li>', ''), ('- \d -', '\t'), (' - ', '\t'), ('\.wav.*', ''), ('_', '\t')])
    line = Path(html.unescape(line)).name
    line = subPairs2(SUB_PAIRS, line)
    print("line: {}".format(line))
    infoAr = line.split('\t')
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

    diskNum = int(diskNumStr)
    if 0 <= diskNum < len(titleAr):
        title = titleAr[diskNum].split('\t')[1].strip()
        return title
    else:
        print("Invalid value, try again")
        return(selectTitle(titleAr))

def findTitleYouTube(artist, track):
    yt = YTMusic()
    search_key = '"' + artist + '" "' + track + '"'

    search_results = yt.search(search_key, "albums")
    print("YouTube search for -{}- found {} items".format(search_key, len(search_results)))

    choices =[]
    releases = []
    releaseTitle = None
    singleTitle = None
    for item in search_results:
        artists = ''
        for artist_row in item.get('artists', []):
            artists = artist_row['name'] + ", "

        #print("item: {}, {}".format(artists, item['title']))

        if artists.lower().find(artist.lower()) >= 0:
            releaseTitle = item['title']
            key = '{} -\t {}'.format(artists, releaseTitle)
            if track == releaseTitle:
                singleTitle = key # use iff there are no other hits
            elif releaseTitle not in releases:
                choices.append(key)
                releases.append(releaseTitle)

    if (len(choices) == 0) & (singleTitle == True):
        releastTitle = singleTitle
    elif len(choices) > 1:
        releaseTitle = selectTitle(artist, track, choices)

    return releaseTitle


def findTitleDiscogs(artist, track):
    #print("Find: {} - {}".format(artist, track))
    #recording:It's five o'clock && artist:Aphrodite's Child&fmt=json&inc=
    query = 'recording:"{}" && artist:"{}"'.format(track, artist)
    url = 'https://musicbrainz.org/ws/2/recording/?limit=40&query=' + urllib.parse.quote_plus(query)
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
        title = findTitleDiscogs(artist, track)

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

if __name__ == '__main__':
    #global playlist_file_name

    playlist_file_name = sys.argv[1] if len(sys.argv) == 2 else None

    #parse_args(sys.argv[1:])
    if len(sys.argv) <= 1:
        print("Usage: {} <PLAYLIST_HTML_FILE or <ARTIST> <TRACK>".format(sys.argv[0]))
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

    result = ''
    isDirty = False
    tracks = []
    # first extract & quit if incomplete line is found.
    for line in lines:
        if (line.find('<li>') < 0) | (line.find('vlc://pause') > 0):
            continue

        artist, track, release, label = getTrackInfo(line)
        if (artist is None) | (track is None):
            print("Invalid line: " + line)
            sys.exit(0)
        else:
            tracks.append((artist, track, release, label))

    lineNum = 0
    for line in tracks:
        artist, track, release, label = line
        if lineNum % 8 == 0:
            result = result + "break\tbreak\tbreak\tbreak\n"

        if release is None:
            time.sleep(1) # throttle the requests
            release = findTitle(artist, track)

        newLine = '{}\t{}\t{}\t{}\n'.format(artist, track, release, label)
        result = result + newLine
        lineNum = lineNum + 1

    new_file_name = playlist_file_name + '_new'
    new_file = open(new_file_name, 'w')
    new_file.write(result)
    new_file.close()







    
