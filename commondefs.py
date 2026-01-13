from os.path import expanduser
import math

# download directory to the staging dir
DJT_DOWNLOAD_DIR = expanduser("~") + "/Music/djtool/active"
ZOOKEEPER_TIMEOUT_SECONDS = 5
        
PAUSE_FILE = 'PAUSE'
MIC_BREAK_FILE = 'MIC_BREAK'
        
def is_stop_file(file_name):
    return file_name == PAUSE_FILE or file_name == MIC_BREAK_FILE

def is_mic_break_file(file_name):
    return file_name == MIC_BREAK_FILE

def is_pause_file(file_name):
    return file_name == PAUSE_FILE

def HMS_from_seconds(seconds):
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    hms_str = f'{math.floor(hours):d}:{math.floor(minutes):02d}:{math.floor(secs):02d}'
    return hms_str

def seconds_from_HMS(time_hms):
    seconds = 0
    timeAr = time_hms.split(':')
    if len(timeAr) == 3:
        seconds =  int(timeAr[0])*60*60 + int(timeAr[1])*60 + int(timeAr[2])
    else:
        seconds =  int(timeAr[0])*60 + int(timeAr[1])

    return seconds


