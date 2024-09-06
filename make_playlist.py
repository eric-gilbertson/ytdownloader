#!/usr/bin/python3
# this file checks the show archvie for the files listed in the input file
# specified with the -f argument. show length is 1 hour and it can be 
# overridden with the -l argument.
#
import os, getopt, sys, http.client, json, glob, urllib, time
from urllib import request, parse

playlist_file_name = None

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

def findDiskTitle(artist, track):
    #print("Find: {} - {}".format(artist, track))
    #recording:It's five o'clock && artist:Aphrodite's Child&fmt=json&inc=
    query = 'recording:"{}" && artist:{}'.format(track, artist)
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

    parse_args(sys.argv[1:])
    if len(sys.argv) <= 1:
        print("Usage: {} <PLAYLIST_FILE>".format(sys.argv[0]))
    elif playlist_file_name is None or not os.path.exists(playlist_file_name):
        print("Error: input file -{}- does not exist.".format(playlist_file_name))
        sys.exit(1)

    playlist_file = open(playlist_file_name)
    lines = playlist_file.readlines()

    result = ''
    isDirty = False
    for line in lines:
        if line[0] == '#' or line.find("break") == 0:
            result = result + line
            continue
          
        fieldAr = line.split('\t')
        fieldCnt = len(fieldAr)

        time.sleep(1)

        if fieldCnt < 2:
            print("Invalid line: {}".format(line))
        elif fieldCnt == 2 or (fieldCnt > 2 and len(fieldAr[2].strip()) == 0):
            artist = fieldAr[0].strip()
            track = fieldAr[1].strip()
            release = findDiskTitle(artist, track)
            if release is not None:
                line = '{}\t{}\t{}\n'.format(artist, track, release)
                isDirty = True

        result = result + line

    new_file_name = playlist_file_name + '_new'
    new_file = open(new_file_name, 'w')
    new_file.write(result)
    new_file.close()







    
