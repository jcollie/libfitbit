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
    global exit
    exit = True

@command('help', 'Print possible commands')
def print_help():
    for cmd in sorted(helps.keys()):
        print '%s\t%s' % (cmd, helps[cmd])

while not exit:
    input = raw_input('> ')
    input = input.split(' ')
    try:
        f = cmds[input[0]]
    except KeyError:
        print 'Command %s not known' % input[0]
        print_help()
        continue
    f(*input[1:])
