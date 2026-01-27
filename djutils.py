import datetime

def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    msg = f'{timestr}:  {msg}'
    print(msg)
    with open('/tmp/djplayer_log.txt', 'a') as logfile:
        logfile.write(msg + '\n')
