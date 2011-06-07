#!/usr/bin/python
"""
Invoke an action from a parsed mail reply. Useful for handling a reply
to an automatic notification from a website (for example).

Options:
    --debug                            Debug mail parsing
    --mail-error                       Mail action errors back to sender
    --bodyfilter-rst2html              Pass body through a rst2html filter

    --quoted-firstline-re='REGEXP'     Regexp for first line of quoted text
                                       Default: $DEFAULT_QUOTED_FIRSTLINE_RE

    --quoted-actiontoken-re='REGEXP'   Regexp for action token in qouted text
                                       Default: $DEFAULT_QUOTED_ACTIONTOKEN_RE

    --auth-sender=SECRET | PATH        Authenticate sender with secret
                                       Accepts a string value or a file path

Action API:
    
    (echo title; cat body) | action action_path urlencode(sender_email)

"""
import os
from os.path import *

import sys
import getopt

import re
from docutils import core, utils
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

RST2HTML_EXAMPLE = \
"""
Basic self-documenting ReStructured Text example
================================================

Don't let the name scare you. RST (ReStructured Text) is merely a very
simple yet clever human readable plain text format which can be
automatically converted into HTML (and other formats). This
explanation of RST formatting also doubles as an example. 

To see this example in HTML go to:

http://www.turnkeylinux.org/rst-example.html

Paragraphs
----------

Paragraphs are just regular plain text paragraphs. Nothing special
about them. The only rule is that paragraphs are separated by an empty
line.

This is a new paragraph.

Links
-----

Several link formats are available.

A naked link: http://www.example.com/

A link to `My favorite search engine <http://www.google.com>`_.

Another link to Ubuntu_ in a different format.

.. _Ubuntu: http://www.ubuntu.com/            
                   
Headlines
---------

We decide something is a headline when it looks like it in plain text.

Technically this means the next line has a row of characters (e.g., -
= ~) of equal length. You've already seen four headline examples
above. It doesn't matter which characters you use so long as they are
not alphanumerics (letters A-Z or numbers 0-9). To signify a deeper
headline level, just use different underline character.

Preformatted text
-----------------

Notice the indentation of the text below and the double colon (I.e.,
::) at the end of this line::

    Preformatted text
    preserves formatting of
    newlines

    Great for code, 
    poetry,
    or command line output...

    $ ps

      PID TTY          TIME CMD
      551 ttyp9    00:00:00 bash
    28452 ttyp9    00:00:00 ps

Lists
-----

An *ordered* list of items:

1) A short list item.

2) One great long item with no newlines or whitespace. Garbage filler: Proin ac sem. Sed massa. Phasellus bibendum dui eget ligula. Vivamus quam quam, adipiscing convallis, pellentesque ut, porta quis, magna.

3) A long item, formatted so that all new lines align with the first.
   Garbage filler: Nam dapibus, neque quis feugiat fringilla, nunc
   magna ultrices leo, vitae sagittis augue quam vel nibh.  Praesent
   vulputate volutpat ligula. Aenean facilisis massa nec nibh.

An *unordered* list of items:

* A list item formatted as one long line. Garbage filler: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Suspendisse risus quam, semper sit amet, posuere et, porttitor in, urna.

* A list item formatted as several lines aligned with the first.
  Garbage filler: Vivamus tincidunt. Etiam quis est sit amet velit
  rutrum viverra.  Curabitur fringilla. Etiam id erat. Etiam posuere
  lobortis augue.

Emphasis
--------

You emphasize a word or phase by putting stars around it. Like *this*.

Single stars provide *weak* emphasis, usually rendered in italics. 

Double stars provide **strong** emphasis, usually rendered in bold.
"""

                   
def rst2html(input_string, initial_header_level=2):
    overrides = {'initial_header_level': initial_header_level,
                 'halt_level': 2 }
    try:
        parts = core.publish_parts(source=input_string, writer_name='html',
                                   settings_overrides=overrides) 
    except utils.SystemMessage, e:
        raise Error(str(e) + "\n\n" + RST2HTML_EXAMPLE.strip())

    return parts['body']

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

    print >> sys.stderr, "Usage: cat mail.eml | %s [-options]" % sys.argv[0]
    tpl = string.Template(__doc__.strip()).substitute(DEFAULT_QUOTED_FIRSTLINE_RE=DEFAULT_QUOTED_FIRSTLINE_RE, 
                                                      DEFAULT_QUOTED_ACTIONTOKEN_RE=DEFAULT_QUOTED_ACTIONTOKEN_RE)
    print >> sys.stderr, tpl

    sys.exit(1)

def sendmail(sender, recipient, subject, body):
    email = MIMEText(body)
    email['From'] = sender
    email['To'] = recipient
    email['Subject'] = subject

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
    opt_bodyfilter_rst2html = False
    opt_quoted_firstline_re = DEFAULT_QUOTED_FIRSTLINE_RE
    opt_quoted_actiontoken_re = DEFAULT_QUOTED_ACTIONTOKEN_RE

    auth_sender = None

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'h', 
                                       [ 'auth-sender=',
                                         'quoted-firstline-re=',
                                         'quoted-actiontoken-re=',
                                         'bodyfilter-rst2html',
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

        if opt == '--bodyfilter-rst2html':
            opt_bodyfilter_rst2html = True

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

        if opt_bodyfilter_rst2html:
            reply = rst2html(reply)

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