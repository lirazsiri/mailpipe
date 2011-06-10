#!/usr/bin/python

import sys

args = sys.argv[1:]
if args:
    if args[0] in ('-h', '--help'):
        print >> sys.stderr, "Syntax: %s [ error ]"
        sys.exit(1)

    print >> sys.stderr, "Simulated error: " + " ".join(args)
    sys.exit(1)

print sys.stdin.read().upper(),
