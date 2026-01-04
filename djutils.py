import datetime

def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    with open('/tmp/djplayer_log.txt', 'a') as logfile:
        logfile.write(timestr + msg + '\n')



