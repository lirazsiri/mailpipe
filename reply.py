#!/usr/bin/python
"""
Invoke an action from a parsed mail reply. Useful for handling a reply
to an automatic notification from a website (for example).

Options:
    --debug                            Debug mail parsing
    --mail-error                       Mail action errors back to sender
    --bodyfilter filter-command        Pass body through filter-command
                                       (triggers error if exitcode != 0)

    --quoted-firstline-re='REGEXP'     Regexp for first line of quoted text
                                       Default: $DEFAULT_QUOTED_FIRSTLINE_RE

    --quoted-actiontoken-re='REGEXP'   Regexp for action token in qouted text
                                       Default: $DEFAULT_QUOTED_ACTIONTOKEN_RE

    --auth-sender=SECRET | PATH        Authenticate sender with secret
                                       Accepts a string value or a file path

Action command interface:
    
    (echo title; cat body) | action action_path urlencode(sender_email)

Example setup:

    useradd reply-handler
    su --login reply-handler

    mkdir bin
    ln -s /usr/share/mailpipe/contrib/drupal_post_comment.php bin/post_comment

    echo mysecretpassword > secret
    chmod 600 secret

    # setup mail forward rule (works with postfix)
    cat > $$HOME/.forward << 'EOF'
    "| PATH=$$HOME/bin:$$PATH mailpipe-reply --auth-sender=$$HOME/secret --mail-error post_comment"
    EOF

"""
import os
from os.path import *

import sys
import getopt

import re
import string

from commands import mkarg
from popen2 import Popen4
from subprocess import Popen, PIPE

import email
from email.mime.text import MIMEText

import sha

from StringIO import StringIO
import traceback

import urllib

DEFAULT_QUOTED_FIRSTLINE_RE = r'\| '
DEFAULT_QUOTED_ACTIONTOKEN_RE = r'https?://\S*?/([_\w\d\#\/\-]+)\s'

class Error(Exception):
    pass

class FilterCommand:
    def __init__(self, command):
        self.command = command

    def __call__(self, s):
        child = Popen(self.command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr) = child.communicate(s)
        if child.returncode != 0:
            raise Error("Error from filter: %s\n%s" % (self.command, stderr))

        return stdout

def get_sender_address(msg):
    sender_address = msg['from']
    m = re.search(r'<(.*)>', sender_address)
    if m:
        sender_address = m.group(1)

    def filter_legal(s):
        return re.sub(r'[^\w\d\.\-@+_]', '', s)

    return filter_legal(sender_address)

def get_title(title):
    m = re.match(r'^(.*?)(?:[\s\(])?\bRe:', title, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()

    return title
    
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

def get_action_token(quoted, quoted_actiontoken_re):
    m = re.search(quoted_actiontoken_re, quoted) 
    if not m:
        raise Error("couldn't match regexp for quoted action token /%s/" % quoted_actiontoken_re)

    return m.group(1)

def usage(e=None):
    if e:
        print >> sys.stderr, "error: " + str(e)

    print >> sys.stderr, "Usage: cat mail.eml | %s [-options] action-command" % sys.argv[0]
    tpl = string.Template(__doc__.strip()).substitute(DEFAULT_QUOTED_FIRSTLINE_RE=DEFAULT_QUOTED_FIRSTLINE_RE, 
                                                      DEFAULT_QUOTED_ACTIONTOKEN_RE=DEFAULT_QUOTED_ACTIONTOKEN_RE)
    print >> sys.stderr, tpl

    sys.exit(1)

def sendmail(sender, recipient, subject, body):
    email = MIMEText(body)
    email['From'] = sender
    email['To'] = recipient
    email['Subject'] = subject

    if os.system("which sendmail > /dev/null") != 0:
        os.environ['PATH'] += ':/usr/local/sbin:/usr/sbin'

    Popen("sendmail -t", shell=True, stdin=PIPE).communicate(str(email))

class AuthSender:
    def __init__(self, secret):
        self.secret = secret

    def __call__(self, msg, sender_address, action_token):
        m = re.search(r'\((.*?)\)', msg['to'])
        if not m:
            raise Error("expected auth token in the email's To: field")
        tok1 = m.group(1)
        tok2 = sha.sha(":".join([self.secret, sender_address, action_token])).hexdigest()[:8]

        if tok1 != tok2:
            raise Error("invalid authentication token in To field (%s)" % tok1)

def main():
    opt_debug = False
    opt_mailerror = False
    opt_quoted_firstline_re = DEFAULT_QUOTED_FIRSTLINE_RE
    opt_quoted_actiontoken_re = DEFAULT_QUOTED_ACTIONTOKEN_RE

    bodyfilter = None
    auth_sender = None

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'h', 
                                       [ 'auth-sender=',
                                         'quoted-firstline-re=',
                                         'quoted-actiontoken-re=',
                                         'bodyfilter=',
                                         'mail-error',
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

        if opt == '--mail-error':
            opt_mailerror = True

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
    sender_address = get_sender_address(msg)

    title = get_title(msg['subject'])

    try:
        reply, quoted = split_body(msg.get_payload(), opt_quoted_firstline_re)
        action_token = get_action_token(quoted, opt_quoted_actiontoken_re)

        if auth_sender:
            auth_sender(msg, sender_address, action_token)

        if bodyfilter:
            reply = FilterCommand(bodyfilter)(reply)

        command = action_command + " %s %s" % (mkarg(action_token), mkarg(urllib.quote(msg['from'])))
        if opt_debug:
            print "COMMAND: " + command
            print "TITLE: " + title
            print
            print reply
            return

        child = Popen4(command)
        print >> child.tochild, title
        print >> child.tochild, reply
        child.tochild.close()

        command_output = child.fromchild.read()
        error = child.wait()

        if error != 0:
            raise Error("non-zero exitcode (%s) for command: %s\n\n%s" % 
                        (os.WEXITSTATUS(error), command, command_output))

        if command_output:
            print command_output,

    except Exception, e:
        if not opt_mailerror:
            raise

        sio = StringIO()
        traceback.print_exc(file=sio)

        sendmail(msg['to'], msg['from'], 
                 'Error handling reply: ' + msg['subject'],
                 sio.getvalue())

if __name__ == "__main__":
    main()
