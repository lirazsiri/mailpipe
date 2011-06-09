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

import shlex

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

class UNDEFINED:
    pass

def property_rw(func):
    return property(func, func)

class Context(object):
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
    def _file_str(path, s=UNDEFINED):
        if s is UNDEFINED:
            if not exists(path):
                return None

            return file(path).read().rstrip()

        else:
            if s is None:
                if exists(path):
                    os.remove(path)
            else:
                fh = file(path, "w")
                print >> fh, s
                fh.close()

    @property_rw
    def id(self, val=UNDEFINED):

        def fmt(uid, gid, groups):
            id = "%d:%d:%s" % (uid, gid, ",".join([ str(group) 
                                                    for group in groups ]))
            return id

        def parse(s):
            uid, gid, groups = s.split(':')
            groups = [ int(group) for group in groups.split(',') ]
            return int(uid), int(gid), groups

        if val and val is not UNDEFINED:
            uid, gid, groups = val
            val = fmt(uid, gid, groups)

        retval = self._file_str(self.subpath.id, val)
        if retval:
            return parse(retval)

    @property_rw
    def env(self, val=UNDEFINED):
        def fmt(env):
            sio = StringIO()
            for var, val in env.items():
                print >> sio, "%s=%s" % (var, val)

            return sio.getvalue()

        def parse(s):
            return dict([ line.split('=', 1) for line in s.splitlines() ])

        if val and val is not UNDEFINED:
            val = fmt(val)

        retval = self._file_str(self.subpath.env, val)
        if retval:
            return parse(retval)

    @property_rw
    def exitcode(self, val=UNDEFINED):
        if val and val is not UNDEFINED:
            val = str(val)

        retval = self._file_str(self.subpath.exitcode, val)
        if retval is not None:
            return int(retval)

    @property_rw
    def command(self, val=UNDEFINED):
        def fmt(argv):
            if not argv:
                return ""

            args = argv[1:]

            for i, arg in enumerate(args):
                if re.search(r"[\s'\"]", arg):
                    args[i] = commands.mkarg(arg)
                else:
                    args[i] = " " + arg

            return argv[0] + "".join(args)

        def parse(s):
            return shlex.split(s)

        if val and val is not UNDEFINED:
            val = fmt(val)

        retval = self._file_str(self.subpath.command, val)
        if retval is not None:
            return parse(retval)

    @property_rw
    def stdin(self, val=UNDEFINED):
        return self._file_str(self.subpath.stdin, val)

    @property_rw
    def stdout(self, val=UNDEFINED):
        return self._file_str(self.subpath.stdout, val)

    @property_rw
    def stderr(self, val=UNDEFINED):
        return self._file_str(self.subpath.stderr, val)

    def save(self, input=None, command=None):
        makedirs(self.path)

        try:
            os.symlink(sys.argv[0], self.subpath.rerun)
        except OSError:
            pass

        self.id = (os.getuid(), os.getgid(), os.getgroups())
        self.env = os.environ

        self.stdin = input
        if command:
            self.command = command

            def run(command, input=None):
                try:
                    child = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                    stdout, stderr = child.communicate(input)

                    return stdout, stderr, child.returncode

                except OSError, e:
                    return "", str(e), None

            self.stdout, self.stderr, self.exitcode = run(command, input)

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

