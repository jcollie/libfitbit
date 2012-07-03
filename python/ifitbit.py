#! /usr/bin/env python

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

from antprotocol.bases import FitBitANT
from fitbit import FitBit

base = None
tracker = None

def checktracker(fn):
    def wrapped(*args):
        if tracker is None:
            print "No tracker, initialize first"
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
    base = FitBitANT(debug=debug)
    if not base.open():
        print "No device connected."
        base = None
        return
    tracker = FitBit(base)
    tracker.init_tracker_for_transfer()

@command('close', 'Close all connections')
def close():
    global base, tracker
    if base is not None:
        print "Closing connctions"
        base.close()
    base = None
    tracker = None

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
def read_bank(index):
    idx = int(index)
    data = tracker.run_data_bank_opcode(idx)
    def pprint(data):
        print ' '.join(["%02X" % x for x in data])
    {0: tracker.parse_bank0_data,
     1: tracker.parse_bank1_data,
     2: tracker.parse_bank2_data,
#     3: tracker.parse_bank3_data,
#     4: tracker.parse_bank4_data,
#     5: tracker.parse_bank5_data,
     6: tracker.parse_bank6_data,
    }.get(idx, pprint)(data)

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
        exit = True

close()
