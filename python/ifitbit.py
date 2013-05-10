#! /usr/bin/env python

import traceback, sys

exit = False

cmds = {}
helps = {}

def command(cmd, help):
    def decorator(fn):
        cmds[cmd] = fn
        helps[cmd] = help
        def wrapped(*args):
            return fn(*args)
        return wrapped
    return decorator

@command('exit', 'Quit...')
def quit():
    print 'Bye !'
    global exit
    exit = True

@command('help', 'Print possible commands')
def print_help():
    for cmd in sorted(helps.keys()):
        print '%s\t%s' % (cmd, helps[cmd])

from antprotocol.connection import getConn
from antprotocol.protocol import ANT
from fitbit import FitBit
import time

base = None
tracker = None

def checktracker(fn):
    def wrapped(*args):
        if tracker is None:
            print "No tracker, initialize first"
            return
        return fn(*args)
    return wrapped

def checkinfo(fn):
    def wrapped(*args):
        if tracker.hardware_version is None:
            print "You first need to request the tracker info (info)"
            return
        return fn(*args)
    return wrapped

@command('init', 'Initialize the tracker')
def init(*args):
    global tracker, base
    debug = False
    if len(args) >= 1:
        debug = bool(int(args[0]))
        if debug: print "Debug ON"
    conn = getConn()
    if conn is None:
        print "No device connected."
        return
    base = ANT(conn)
    tracker = FitBit(base)
    tracker.init_tracker_for_transfer()

@command('close', 'Close all connections')
def close():
    global base, tracker
    if base is not None:
        print "Closing connection"
        base.connection.close()
    base = None
    tracker = None

@command('test', 'Run a test from the old fitbit.py')
def test():
    global base
    if base is None:
        conn = getConn()
        if conn is None:
            print "No devices connected!"
            return 1
        base = ANT(conn)
    device = FitBit(base)

    device.init_tracker_for_transfer()

    device.get_tracker_info()
    # print device.tracker

    device.parse_bank2_data(device.run_data_bank_opcode(0x02))
    print "---"
    device.parse_bank0_data(device.run_data_bank_opcode(0x00))
    device.run_data_bank_opcode(0x04)
    d = device.run_data_bank_opcode(0x02) # 13
    for i in range(0, len(d), 13):
        print ["%02x" % x for x in d[i:i+13]]
    d = device.run_data_bank_opcode(0x00) # 7
    print ["%02x" % x for x in d[0:7]]
    print ["%02x" % x for x in d[7:14]]
    j = 0
    for i in range(14, len(d), 3):
        print d[i:i+3]
        j += 1
    print "Records: %d" % (j)
    device.parse_bank1_data(device.run_data_bank_opcode(0x01))

    # for i in range(0, len(d), 14):
    #     print ["%02x" % x for x in d[i:i+14]]
    base.connection.close()
    base = None

@command('>', 'Run opcode')
@checktracker
def opcode(*args):
    args = list(args)
    while len(args) < 7:
        # make it a full opcode
        args.append('0')
    code = [int(x, 16) for x in args[:7]]
    payload = [int(x, 16) for x in args[7:]]
    print '==> ', code #' '.join(['%02X' % x for x in code])
    if payload:
        print '  -> ', ' '.join(['%02X' % x for x in payload])
    res = tracker.run_opcode(code, payload)
    print '<== ',' '.join(['%02X' % x for x in res])

@command('info', 'Get tracker info')
@checktracker
def get_info():
    tracker.get_tracker_info()
    print tracker

@command('read', 'Read data bank')
@checktracker
@checkinfo
def read_bank(index):
    idx = int(index)
    data = tracker.run_data_bank_opcode(idx)
    def pprint(data):
        print ' '.join(["%02X" % x for x in data])
    {0: tracker.parse_bank0_data,
     1: tracker.parse_bank1_data,
     2: tracker.parse_bank2_data,
#     3: tracker.parse_bank3_data,
     4: tracker.parse_bank4_data,
#     5: tracker.parse_bank5_data,
     6: tracker.parse_bank6_data,
    }.get(idx, pprint)(data)

@command('pr5', 'Periodic read 5')
@checktracker
def pr5(sleep = '5', repeat = '100'):
    sleep = int(sleep)
    repeat = int(repeat)
    while repeat > 0:
        read_bank(5)
        time.sleep(sleep)
        repeat -= 1

@command('erase', 'Erase data bank')
@checktracker
def erase_bank(index, tstamp=None):
    idx = int(index)
    if tstamp is not None:
        tstamp = int(tstamp)
    data = tracker.erase_data_bank(idx, tstamp)
    if data != [65, 0, 0, 0, 0, 0, 0]:
        print "Bad", data
        return
    print "Done"

while not exit:
    input = raw_input('> ')
    input = input.split(' ')
    try:
        f = cmds[input[0]]
    except KeyError:
        print 'Command %s not known' % input[0]
        print_help()
        continue
    try:
        f(*input[1:])
    except Exception, e:
        # We need that to be able to close the connection nicely
        print "BaD bAd BAd", e
        traceback.print_exc(file=sys.stdout)
        exit = True

close()
