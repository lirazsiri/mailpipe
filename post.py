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
import sys
import getopt

import re
import string

import email

from StringIO import StringIO
import traceback

from action import Action
from sendmail import sendmail

def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)

    print >> sys.stderr, "Usage: cat mail.eml | %s [-options] action-command" % sys.argv[0]
    print >> sys.stderr, __doc__.strip()

    sys.exit(1)

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
    action = Action(action_command, bodyfilter)

    try:
        output = action(msg)
    except Exception, e:
        if not opt_mailback_error:
            raise

        sio = StringIO()
        traceback.print_exc(file=sio)

        sendmail(msg['to'], msg['from'], 
                 'Error handling post: ' + msg['subject'], sio.getvalue())
        
        sys.exit(1)

    if output:
        if opt_mailback_output:
            sendmail(msg['to'], msg['from'], 
                     'Re: ' + msg['subject'], output)
                     
        else:
            print output,

if __name__ == "__main__":
    main()
