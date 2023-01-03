#!/usr/local/bin/python3
# trims leading & trailing silence to GAP_SECONDS and saves original file in 
# <FILE_NAME>.sav. no change if gaps are less than GAP_SECONDS.

import os, sys, subprocess, datetime, glob, pathlib

# return time length in seconds of an mp3 file using ffmpeg or -1 if invalid.
# assumes user has ffmpeg in PATH.
def execute_ffmpeg_command(cmd):
    cmd = "/usr/local/bin/ffmpeg -hide_banner " + cmd
    #print("Execute: {}".format(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    p_status = p.wait()
    err = str(err)
    #print("Execute: returned {}, {}".format(output, err))
    return p_status

# return start gap, end gap and duration in seconds
def get_gap_info(filePath):
    start_gap = end_gap = duration = 0
    cmd = '/usr/local/bin/ffmpeg -hide_banner -i "{}"  -af silencedetect=n=-40dB:d=2.0 -f null -'.format(filePath)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    p_status = p.wait()
    result = str(err)

    if result.find("Duration:") > 0:
        idx1 = result.index('Duration:') + 9
        idx2 = result.index(',', idx1)
        time_str = result[idx1:idx2].strip()
        time = datetime.datetime.strptime(time_str, '%H:%M:%S.%f')
        duration = time.second + time.minute * 60 + time.hour * 3600

    silence_start_idx = result.find('silence_start: ') + 15
    have_end_gap = False
    while silence_start_idx > 15:
        silence_start_idx2 = result.find("\\", silence_start_idx)
        start_time = result[silence_start_idx:silence_start_idx2]
        start_time = float(start_time)
        silence_end_idx = int(result.find('silence_end: ', silence_start_idx) + 13)
        silence_end_idx2 = result.find('|', silence_end_idx)
        end_time = result[silence_end_idx:silence_end_idx2]
        end_time = float(end_time)

        if start_time == 0:
            start_gap = end_time
        elif abs(duration - end_time) < 1:
            end_gap = end_time - start_time

        silence_start_idx = result.find('silence_start: ', silence_start_idx) + 15

    return start_gap, end_gap, duration

def trim_audio(srcFile):
    GAP_SECONDS = 2
    start_gap, end_gap, duration = get_gap_info(srcFile)
    start_trim = max(start_gap - GAP_SECONDS, 0)
    end_trim = max(end_gap - GAP_SECONDS, 0)
    if start_trim > 0 or end_trim > 0:
        srcpath = pathlib.Path(srcFile)
        tmpFile = srcFile +  ".trim" + srcpath.suffix
        print("trim file: {}, {:0.2f}, {:0.2f}".format(srcFile, start_trim, end_trim))
        cmd = ' -y -i "{}" -ss {} -to {} -c:a copy "{}"'.format(srcFile, start_trim, duration - end_trim, tmpFile)
        if execute_ffmpeg_command(cmd) != 0:
            print("trim error: {}".format(cmd))
            return None
        
        saveFile = os.path.dirname(srcFile) + srcpath.stem + ".trim" + srcpath.suffix
        if not os.path.exists(saveFile): 
            os.rename(srcFile, saveFile) # save only the true ref file & don't overwrite

        os.rename(tmpFile, srcFile)
    else:
        print("no change: {}, {:0.2f}, {:0.2f}".format(srcFile, start_trim, end_trim))
        


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: [info|trim] <FILE_NAME>".format(sys.argv[0]))
        sys.exit(0)

    op = sys.argv[1]
    files = [sys.argv[2]]
    if os.path.isdir(sys.argv[2]):
        files = glob.glob(sys.argv[2] + "/*.wav")

    if op == 'info':
        for file in files:
            start_gap, end_gap, duration = get_gap_info(file)
            hours = duration // 60
            mins = duration % 60
            print("{}: {:0.2f}, {:0.2f}, {}:{:02d} ({})".format(file, start_gap, end_gap, hours, mins, duration))
    elif op == 'trim':
        for file in files:
            trim_audio(file)
            

