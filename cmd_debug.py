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


class Context:
    class ContextPaths:
        SUBDIRS = ['command', 'id', 'env', 'stdin', 'stdout', 'stderr', 'exitcode', 'rerun']
        def __init__(self, path):
            self.path = path
            for subdir in self.SUBDIRS:
                setattr(self, subdir, join(path, subdir))

    def __init__(self, path):
        self.path = path
        self.subpath = self.ContextPaths(path)

    @staticmethod
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

    @staticmethod
    def fmt_id():
        id = "%d:%d:%s" % (os.getuid(), os.getgid(), 
                           ",".join([ str(group) for group in os.getgroups() ]))
        return id

    @staticmethod
    def fmt_env():
        sio = StringIO()
        for var, val in os.environ.items():
            print >> sio, "%s=%s" % (var, val)

        return sio.getvalue()

    @staticmethod
    def run(command, input=None):
        try:
            child = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdout, stderr = child.communicate(input)

            return stdout, stderr, child.returncode

        except OSError, e:
            return "", str(e), None

    def save(self, input=None, command=None):
        makedirs(self.path)
        subpath = self.subpath

        print >> file(subpath.id, "w"), self.fmt_id()
        print >> file(subpath.env, "w").write(self.fmt_env())

        if input:
            file(subpath.stdin, "w").write(input)

        try:
            os.symlink(sys.argv[0], subpath.rerun)
        except OSError:
            pass

        if command:
            print >> file(subpath.command, "w"), self.fmt_command(command)

            stdout, stderr, exitcode = run(command, input)
            if stdout:
                file(subpath.stdout, "w").write(stdout)

            if stderr:
                file(subpath.stderr, "w").write(stderr)

            if exitcode is not None:
                print >> file(subpath.exitcode, "w"), "%d" % exitcode

def debug():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print >> sys.stderr, "Syntax: %s command ..." % sys.argv[0]
        print >> sys.stderr, __doc__.strip()

        sys.exit(1)

    command = args
    input = sys.stdin.read()

    tmpdir = os.environ.get("MAILPIPE_TMPDIR", "/tmp/mailpipe-debug")
    digest = md5.md5(`command` + input).hexdigest()
    path = os.path.join(tmpdir, digest)

    state = Context(path)
    state.save(input, command)

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

