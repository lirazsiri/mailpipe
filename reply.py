#!/usr/bin/python
"""
Invoke an action from a parsed mail reply. Useful for handling a reply
to an automatic notification from a website (for example).

Options:
    --debug                            Debug mail parsing
    --mailback-error                   Mail action errors back to sender
    --bodyfilter filter-command        Pass body through filter-command
                                       (triggers error if exitcode != 0)

    --quoted-firstline-re='REGEXP'     Regexp for first line of quoted text
                                       Default: $DEFAULT_QUOTED_FIRSTLINE_RE

    --quoted-actiontoken-re='REGEXP'   Regexp for action token in qouted text
                                       Default: $DEFAULT_QUOTED_ACTIONTOKEN_RE

    --auth-sender=SECRET | PATH        Authenticate sender with secret
                                       Accepts a string value or a file path

Action command interface:
    
    (echo title; cat body) | action urlencode(sender_email) action_token

Example setup:

    useradd reply-handler
    su --login reply-handler

    mkdir bin
    ln -s /usr/share/mailpipe/contrib/drupal_post_comment.php bin/post_comment

    echo mysecretpassword > secret
    chmod 600 secret

    # setup mail forward rule (works with postfix)
    cat > $$HOME/.forward << 'EOF'
    "| PATH=$$HOME/bin:$$PATH mailpipe-reply --auth-sender=$$HOME/secret --mailback-error post_comment"
    EOF

"""
import os
from os.path import *

import sys
import getopt

import re
import string

import email

from StringIO import StringIO
import traceback

from sendmail import sendmail

import sha
import urllib
from commands import mkarg
from action import Action

class Error(Exception):
    pass

class AuthSender:
    def __init__(self, secret):
        self.secret = secret

    @staticmethod
    def get_sender_address(sender_address):
        m = re.search(r'<(.*)>', sender_address)
        if m:
            sender_address = m.group(1)

        def filter_legal(s):
            return re.sub(r'[^\w\d\.\-@+_]', '', s)

        return filter_legal(sender_address)

    def __call__(self, msg, action_token):
        sender_address = self.get_sender_address(msg['from'])

        m = re.search(r'\((.*?)\)', msg['to'])
        if not m:
            raise Error("expected auth token in the email's To: field")
        tok1 = m.group(1)
        tok2 = sha.sha(":".join([self.secret, sender_address, action_token])).hexdigest()[:8]

        if tok1 != tok2:
            raise Error("invalid authentication token in To field (%s)" % tok1)

class ReplyAction(Action):
    DEFAULT_QUOTED_FIRSTLINE_RE = r'\| '
    DEFAULT_QUOTED_ACTIONTOKEN_RE = r'https?://\S*?/([_\w\d\#\/\-]+)\s'

    def __init__(self, action_command, bodyfilter=None, auth_sender=None,
                 quoted_firstline_re=None, quoted_actiontoken_re=None):

        Action.__init__(self, action_command, bodyfilter)

        if quoted_firstline_re is None:
            quoted_firstline_re = self.DEFAULT_QUOTED_FIRSTLINE_RE

        if quoted_actiontoken_re is None:
            quoted_actiontoken_re = self.DEFAULT_QUOTED_ACTIONTOKEN_RE

        self.quoted_firstline_re = quoted_firstline_re
        self.quoted_actiontoken_re = quoted_actiontoken_re

        self.auth_sender = auth_sender

    @staticmethod
    def get_title(title):
        m = re.match(r'^(.*?)(?:[\s\(])?\bRe:', title, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()

        return title
        
    @staticmethod
    def split_body(body, quoted_firstline_re):
        """split body into reply and original quoted text"""
        def find_line(lines, pattern):
            pattern = re.compile(pattern)
            for i, line in enumerate(lines):
                if pattern.match(line):
                    return i

        lines = body.splitlines()

        linenum = find_line(lines, '^.\s*' + quoted_firstline_re)
        if linenum < 0:
            raise Error("can't match quoted firstline /%s/" % quoted_firstline_re)

        def rejoin(lines):
            return "\n".join(lines).strip()
        return rejoin(lines[:linenum-1]), rejoin(lines[linenum-1:])

    @staticmethod
    def get_action_token(quoted, quoted_actiontoken_re):
        m = re.search(quoted_actiontoken_re, quoted) 
        if not m:
            raise Error("couldn't match regexp for quoted action token /%s/" % quoted_actiontoken_re)

        return m.group(1)

    def parse_msg(self, msg):
        title = self.get_title(msg['subject'])
        reply, quoted = self.split_body(msg.get_payload(), self.quoted_firstline_re)
        action_token = self.get_action_token(quoted, self.quoted_actiontoken_re)

        if self.auth_sender:
            self.auth_sender(msg, action_token)

        return title, reply, action_token

    def command(self, msg, action_token):
        return self.action_command + " %s %s" % (mkarg(urllib.quote(msg['from'])),
                                                 mkarg(action_token))



def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)

    print >> sys.stderr, "Usage: cat mail.eml | %s [-options] action-command" % sys.argv[0]
    tpl = string.Template(__doc__.strip()).substitute(DEFAULT_QUOTED_FIRSTLINE_RE=ReplyAction.DEFAULT_QUOTED_FIRSTLINE_RE, 
                                                      DEFAULT_QUOTED_ACTIONTOKEN_RE=ReplyAction.DEFAULT_QUOTED_ACTIONTOKEN_RE)
    print >> sys.stderr, tpl

    sys.exit(1)

def main():
    opt_debug = False
    opt_mailback_error = False
    opt_quoted_firstline_re = None
    opt_quoted_actiontoken_re = None

    bodyfilter = None
    auth_sender = None

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'h', 
                                       [ 'auth-sender=',
                                         'quoted-firstline-re=',
                                         'quoted-actiontoken-re=',
                                         'bodyfilter=',
                                         'mailback-error',
                                         'debug'
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

        if opt == '--debug':
            opt_debug = True

        if opt == '--mailback-error':
            opt_mailback_error = True

        if opt == '--bodyfilter':
            bodyfilter = val

        if opt == '--quoted-firstline-re':
            opt_quoted_firstline_re = val

        if opt == '--quoted-actiontoken-re':
            opt_quoted_actiontoken_re = val

        if opt == '--auth-sender':
            if isfile(val):
                val = file(val).readline().strip()

            auth_sender = AuthSender(val)

    msg = email.message_from_string(sys.stdin.read())

    action = ReplyAction(action_command, bodyfilter, auth_sender,
                         opt_quoted_firstline_re, opt_quoted_actiontoken_re)
    try:
        output = action(msg)
    except Exception, e:
        if not opt_mailback_error:
            raise

        sio = StringIO()
        traceback.print_exc(file=sio)

        sendmail(msg['to'], msg['from'], 
                 'Error handling reply: ' + msg['subject'],
                 sio.getvalue())

        sys.exit(1)

    if output:
        print output,

if __name__ == "__main__":
    main()
