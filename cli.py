#!/usr/bin/python
"""
Invoke a cli command from an e-mail

Options:
    -t --timeout=SECONDS   How many seconds before command times out (default: %d)

Example usage:

    cat path/to/test.eml | mail2cli echo "arguments: " | sendmail -t

"""

import os
import re
import sys
import getopt

import email
from popen2 import Popen4
import shlex

from StringIO import StringIO
import time
import signal

from email.mime.text import MIMEText

DEFAULT_TIMEOUT = 60
__doc__ = __doc__ % DEFAULT_TIMEOUT

def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)
    print >> sys.stderr, "syntax: %s [ -options ] command-prefix" % sys.argv[0]
    print >> sys.stderr, __doc__.strip()
    sys.exit(1)

def execute(command, timeout=None):
    p = Popen4(command)
    start = time.time()
    while True:
        err = p.poll()
        if err != -1:
            break
        if timeout and (time.time() - start) > timeout:
            os.kill(p.pid, signal.SIGTERM)
            p.wait()
            break
        time.sleep(0.1)

    output = p.fromchild.read()
    error = p.wait()

    return output, error

def mail2cli(prefix, request, timeout=None):
    command = request.get_payload().strip()

    report = StringIO()

    if report.len:
        print >> report

    command = prefix + shlex.split(command)
    print >> report, "# executing " + `tuple(command)`
    output, error = execute(command, timeout)
    if output:
        print >> report, output.strip()
    if error:
        if os.WIFEXITED(error):
            print >> report, "# exited with error (%d)" % os.WEXITSTATUS(error)
        if os.WIFSIGNALED(error):
            print >> report, "# killed (%d)" % error

    print >> report
    print >> report, "%s wrote:" % re.sub(r'\s+<.*', '', request['From'])
    print >> report, "\n".join([ "> " + line 
                                 for line in request.get_payload().strip().split('\n') ])

    response = MIMEText(report.getvalue())
    response['To'] = request['from']
    if request['cc']:
        response['CC'] = request['cc']
    response['From'] = request['to']
    response['Subject'] = 'Re: ' + request['subject']

    return response

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '-t:h', ['timeout='])
    except getopt.GetoptError, e:
        usage(e)

    opt_timeout = DEFAULT_TIMEOUT
    for opt, val in opts:
        if opt == '-h':
            usage()

        if opt in ('-t', '--timeout'):
            opt_timeout = int(val)

    if not args:
        usage()

    prefix = args

    request = email.message_from_string(sys.stdin.read())
    response = mail2cli(prefix, request, timeout=opt_timeout)

    print response

if __name__ == "__main__":
    main()
