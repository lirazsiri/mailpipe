#!/usr/bin/python
"""
Parse a mail post and pipe through to a command action.

Options:
    --mailback-output                  Mail action output back to sender
    --mailback-error                   Mail action errors back to sender
    --bodyfilter filter-command        Pass body through filter-command
                                       (triggers error if exitcode != 0)

Action command interface:
    
    (echo title; cat body) | action urlencode(sender_email)

"""
import os
from os.path import *

import sys
import getopt

import re
import string

from commands import mkarg
from popen2 import Popen4

import email

from StringIO import StringIO
import traceback

import urllib

from filter import FilterCommand
from sendmail import sendmail

def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)

    print >> sys.stderr, "Usage: cat mail.eml | %s [-options] action-command" % sys.argv[0]
    print >> sys.stderr, __doc__.strip()

    sys.exit(1)

class Error(Exception):
    pass

class MailHandler:
    def __init__(self, action_command, bodyfilter=None):
        self.action_command = action_command
        self.bodyfilter = bodyfilter

    def __call__(self, msg):
        title = msg['subject']
        body = msg.get_payload()

        if self.bodyfilter:
            body = FilterCommand(self.bodyfilter)(body)

        command = self.action_command + " %s" % mkarg(urllib.quote(msg['from']))
        child = Popen4(command)
        print >> child.tochild, title
        print >> child.tochild, body
        child.tochild.close()

        command_output = child.fromchild.read()
        error = child.wait()

        if error != 0:
            raise Error("non-zero exitcode (%s) for command: %s\n\n%s" % 
                        (os.WEXITSTATUS(error), command, command_output))

        return command_output

def main():
    opt_mailback_error = False
    opt_mailback_output = False

    bodyfilter = None
    auth_sender = None

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'h', 
                                       [ 'bodyfilter=',
                                         'mailback-output',
                                         'mailback-error',
                                       ])
                                       
    except getopt.GetoptError, e:
        usage(e)

    if not args:
        usage()

    if len(args) != 1:
        usage("too many arguments")

    action_command = args[0]

    for opt, val in opts:
        if opt == '-h':
            usage()

        if opt == '--mailback-error':
            opt_mailback_error = True

        if opt == '--mailback-output':
            opt_mailback_output = True

        if opt == '--bodyfilter':
            bodyfilter = val

    msg = email.message_from_string(sys.stdin.read())
    handler = MailHandler(action_command, bodyfilter)

    try:
        output = handler(msg)
    except Exception, e:
        if not opt_mailback_error:
            raise

        sio = StringIO()
        traceback.print_exc(file=sio)

        sendmail(msg['to'], msg['from'], 
                 'Error handling post: ' + msg['subject'], sio.getvalue())
        
        sys.exit(1)

    if opt_mailback_output:
        sendmail(msg['to'], msg['from'], 
                 'Re: ' + msg['subject'], output)
                 
    else:
        print output,

if __name__ == "__main__":
    main()
