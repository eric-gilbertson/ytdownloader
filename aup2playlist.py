#!/usr/bin/python3
#
# generates a Zookeeper playlist import file from an Audacity project
# file, e.g. .aup
#
import sys, json, re
import xml.etree.ElementTree as et

def log_it(msg):
   print(msg, flush=True)

def time2Seconds(timeStr):
    timeAr = timeStr.split(':')
    if len(timeAr) != 2:
        log_it("Invalid time value: {}".format(timeStr));
        sys.exit(1)

    seconds = int(timeAr[0])*3600 + int(timeAr[1])*60
    return seconds

def seconds2Time(seconds):
    hours = seconds // 3600
    minutes = (seconds - hours*3600) // 60
    seconds = seconds - hours*3600 - minutes*60
    time = "{:02d}:{:02d}:{:02d})".format(hours, minutes, seconds)
    return time

def parseAupFile(fileName):

    with open(fileName, 'r') as file:
        root = et.fromstring(file.read())

    idx = 0;
    lastTitle = ''
    tracks = []
    for child in root:
        print("tag: {}".format(child.tag))
        if (child.tag.endswith('labeltrack')):
            tracks.append({'created': None, 'type': 'spin'})
        elif (child.tag.endswith('wavetrack')):
            clip = child.find("waveclip")

            title = child.attrib['name']
            if title == lastTitle:
                continue

            lastTitle = title
            title = re.sub("- \d{1,2} -", "-", title)

            titleAr = title.split('-')
            if len(titleAr) < 2:
                titleAr = title.split('_')

            if len(titleAr) < 2:
                titleAr = title.split(' by ')

            if len(titleAr) >= 2:
                artist = titleAr[0].strip()
                track = ' '.join(titleAr[1:]).strip()
            else:
                artist = title
                track = 'UNKNOWN'

            if track.endswith(')'): # prune suffixes like (Radio Edit)
                track = track[0 : track.rfind('(')]
            elif track.endswith(']'):
                track = track[0 : track.rfind('[')]

            clip = child.find("{http://audacity.sourceforge.net/xml/}waveclip")
            if clip:
                seconds = int(float(clip.attrib['offset']))
                print("{} - {}".format(seconds2Time(seconds), track))

            #print("{}: {} by {}".format(idx, track, artist))
            if artist.startswith("silence") or artist.startswith("Label Track"):
                tracks.append({'created':None, 'type': 'spin'})
            else:
                tracks.append({'created':None, 'track':track, 'artist':artist, 'label':'', 'album':'', 'type':'spin'})

            idx += 1

    return tracks


def makeJsonPlaylist(tracks):
    events = []
    for track in tracks:
        events.append(track)

    attributes = {
        'name' : 'Hanging In The Boneyard',
        'date' : '2030-01-01',
        'time' : '1400-1700',
        'airname' : 'Mr. Bones',
        'rebroadcast' : False,
        'events' : events,
    }

    data = {'type':'show', 'attributes': attributes,  }
    data_json = json.dumps(data)
    outFile = open('/Users/Barbara/Downloads/playlist.json', 'w')
    outFile.write("{}\n".format(data_json))


def makeCsvPlaylist(tracks):
    outFile = open('/Users/Barbara/Downloads/playlist.txt', 'w')

    for trackInfo in tracks:
        artist = trackInfo.get('artist')
        track = trackInfo.get('track')
        track = 'silence' if track == None else track
        type = trackInfo.get('type')
        print("track: {}, {}".format(track, artist));
        if type == 'break':
            outFile.write("\n")
        else:
            outFile.write("{}\t{}\t\t\n".format(artist, track))

    outFile.close()

def printDuplicates(tracks):
    trackMap = {}
    idx = 0
    for trackInfo in tracks:
        artist = trackInfo.get('artist')
        track = trackInfo.get('track')
        track = 'silence' if track == None else track
        if track != 'silence' and track in trackMap:
            print("duplicate: {} {}, {}".format(idx, artist, track))
        
        trackMap[track] = True
        idx = idx + 1


def makePlaylists(srcFile, startTime):
    tracks = parseAupFile(srcFile)
    makeCsvPlaylist(tracks)
    makeJsonPlaylist(tracks)
    printDuplicates(tracks)


if __name__ == "__main__":
    argCnt = len(sys.argv) - 1
    if argCnt == 1:
        makePlaylists(sys.argv[1], False)
    elif argCnt == 2:
        makePlaylists(sys.argv[1], sys.argv[2])
    else:
        print("Use: {} <AUP_FILE> [HH:MM]".format(sys.argv[0]))
        sys.exit(1)

