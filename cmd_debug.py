#!/usr/bin/python
"""
Mailpipe debug tool traps input/output for inspection

Environment variables:

    MAILPIPE_TMPDIR     Path where we save debug data
                        Default: /tmp/mailpipe-debug
"""
import sys
import os
from os.path import *
import md5
import re

import commands
import errno

from StringIO import StringIO
from subprocess import Popen, PIPE

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

class DebugPaths:
    SUBDIRS = ['command', 'id', 'env', 'stdin', 'stdout', 'stderr', 'exitcode', 'rerun']
    def __init__(self, path):
        self.path = path
        for subdir in self.SUBDIRS:
            setattr(self, subdir, join(path, subdir))

def fmt_command(argv):
    if not argv:
        return ""

    args = argv[1:]

    for i, arg in enumerate(args):
        if re.search(r"[\s'\"]", arg):
            args[i] = commands.mkarg(arg)
        else:
            args[i] = " " + arg

    return argv[0] + "".join(args)

def fmt_id():
    id = "%d:%d:%s" % (os.getuid(), os.getgid(), 
                       ",".join([ str(group) for group in os.getgroups() ]))
    return id

def fmt_env():
    sio = StringIO()
    for var, val in os.environ.items():
        print >> sio, "%s=%s" % (var, val)

    return sio.getvalue()

def run(command, input=None):
    try:
        child = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = child.communicate(input)

        return stdout, stderr, child.returncode

    except OSError, e:
        return "", str(e), None

def debug():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print >> sys.stderr, "Syntax: %s command ..." % sys.argv[0]
        print >> sys.stderr, __doc__.strip()

        sys.exit(1)

    command = args
    stdin = sys.stdin.read()

    tmpdir = os.environ.get("MAILPIPE_TMPDIR", "/tmp/mailpipe-debug")
    digest = md5.md5(`command` + stdin).hexdigest()

    path = os.path.join(tmpdir, digest)
    makedirs(path)

    paths = DebugPaths(path)
    
    print >> file(paths.id, "w"), fmt_id()
    print >> file(paths.env, "w").write(fmt_env())

    if stdin:
        file(paths.stdin, "w").write(stdin)

    try:
        os.symlink(sys.argv[0], paths.rerun)
    except OSError:
        pass

    if command:
        print >> file(paths.command, "w"), fmt_command(command)

        stdout, stderr, exitcode = run(command, stdin)
        if stdout:
            file(paths.stdout, "w").write(stdout)

        if stderr:
            file(paths.stderr, "w").write(stderr)

        if exitcode is not None:
            print >> file(paths.exitcode, "w"), "%d" % exitcode

def rerun():
    args = sys.argv[1:]
    shell = False
    if args:
        opt = args[0]

        if opt in ("-h", "--help"):
            print >> sys.stderr, "Syntax: %s [ --shell ]" % sys.argv[0]
            sys.exit(1)

        if opt == "--shell":
            shell = True

def main():
    if basename(sys.argv[0]) == "rerun":
        return rerun()

    debug()

if __name__ == "__main__":
    main()

