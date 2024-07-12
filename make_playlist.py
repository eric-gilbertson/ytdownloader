#!/usr/local/bin/python3
# this file checks the show archvie for the files listed in the input file
# specified with the -f argument. show length is 1 hour and it can be 
# overridden with the -l argument.
#
import os, getopt, sys, http.client, json, glob, urllib
from urllib import request, parse

playlist_file_name = None

def findDiskTitle(artist, track):
    #recording:It's five o'clock && artist:Aphrodite's Child&fmt=json&inc=
    query = 'recording:"{}" && artist:{}'.format(track, artist)
    url = 'https://musicbrainz.org/ws/2/recording/?limit=20&query=' + urllib.parse.quote_plus(query)
    req = request.Request(url, method='GET')
    req.add_header("Accept", "application/json")

    response = request.urlopen(req)
    print("Status: {} and reason: {}".format(response.status, response.reason))

    if response.status != 200:
        print("Musicbrainz error: {}".format(response.status))
        return null

    result = json.loads(response.read())
    for recording in result['recordings']:
        artistName = recording['artist-credit'][0]['name']
        release = recording['releases'][0]
        releaseTitle = release['title']
        print("Found: {}, {}, {}, {}".format(recording['title'], artistName, releaseTitle, recording['score']))

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
    if playlist_file_name is None or not os.path.exists(playlist_file_name):
        print("Error: input file -{}- does not exist.".format(playlist_file_name))
        sys.exit(1)

    playlist_file = open(playlist_file_name)
    lines = playlist_file.readlines()

    for line in lines:
        fieldAr = line.split('\t')
        fieldCnt = len(fieldAr)
        if fieldCnt != 2 or line[0] == '#':
            continue

        print("line: " + line)

        artist = fieldAr[0]
        track  = fieldAr[1]
        findDiskTitle(artist, track)



    
