import datetime
import pathlib


def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    msg = f'{timestr}:  {msg}'
    print(msg)
    with open(get_logfile_path(), 'a') as logfile:
        logfile.write(msg + '\n')


def get_logfile_path():
    return str(pathlib.Path.home()) + "/djtool_log.txt"

