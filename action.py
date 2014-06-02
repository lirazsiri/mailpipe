import os
import urllib

from commands import mkarg
from filter import FilterCommand
from popen2 import Popen4

class Error(Exception):
    pass

import email

import quopri
import base64

import codecs
import string

from htmlentitydefs import name2codepoint

import re

def get_body(message, decrypt=False):
    if not message.is_multipart():
        parts = [ message ]
    else:
        parts = message.get_payload()

    for part in parts:
        payload = part.get_payload()

        content_type = part.get('content-type')
        if decrypt and "PGP MESSAGE" in payload:
            payload = executil.getoutput_popen(["gpg", "--batch"], input=payload)

            if not content_type:
                return payload, None

        content_description = part.get('content-description')
        if content_description and 'encrypted message' in content_description:
            return get_body(email.message_from_string(payload))

        encoding = part.get('content-transfer-encoding')
        if encoding:
            if encoding == 'quoted-printable':
                payload = quopri.decodestring(payload)

            elif encoding == 'base64':
                payload = base64.decodestring(payload)

        if content_type:
            m = re.search(r'charset=([\w\d\-]+)', message['content-type'])
            if m:
                charset = m.group(1)
                try:
                    payload = codecs.decode(payload, charset)
                except:
                    pass

            if 'text/plain' in content_type:
                return payload, content_type

    # go one layer deeper if we can't find a message in the first layer
    if message.is_multipart():
        payload = message.get_payload()
        if payload:
            return get_body(payload[0])

    else:
        return payload, content_type

    raise Error("can't get message body")

def htmlentitydecode(s):
    return re.sub('&(%s);' % '|'.join(name2codepoint),
            lambda m: unichr(name2codepoint[m.group(1)]), s)

def html2txt(buf):
    buf = re.sub(r'\s+', ' ', buf)
    buf = re.sub('<BR\s*/?>', '\n', buf, 0, re.IGNORECASE)

    # strip tags
    buf = re.sub(r'</?\w+[^>]*>', '', buf)

    # strip tag comments
    buf = re.sub(r'<!--[^>]*-->', '', buf)

    buf = htmlentitydecode(buf).replace(u'\xa0', ' ')
    buf = re.sub(r'^[ ]+', '', buf, 0, re.MULTILINE)

    return buf

def get_body_text(msg):
    text, content_type = get_body(msg)

    if content_type:
        if 'text/html' in content_type:
            text = html2txt(text)

    return text

def filter_printable(s):
    return filter(lambda c: c in string.printable, s)

def decode_header(value):
    def simplify_whitespace(s):
        return re.sub(r'[\n\t]+', ' ', s)
    
    value = simplify_whitespace(value)

    value, encoding = email.header.decode_header(value)[0]
    try:
        if encoding:
            value = codecs.decode(value, encoding)
    except:
        pass

    value = simplify_whitespace(value)
    value = filter_printable(value)

    return value

class Action:
    def __init__(self, action_command, bodyfilter=None):
        self.action_command = action_command
        self.bodyfilter = bodyfilter

    def parse_msg(self, msg):
        return msg['subject'], get_body_text(msg)

    def command(self, msg):
        return self.action_command + " %s" % mkarg(urllib.quote(msg['from']))

    def __call__(self, msg):
        vals = self.parse_msg(msg)
        title, body = vals[:2]
        
        if self.bodyfilter:
            body = FilterCommand(self.bodyfilter)(body)

        command = self.command(msg, *vals[2:])
        child = Popen4(command)
        print >> child.tochild, title
        print >> child.tochild, body
        child.tochild.close()

        command_output = child.fromchild.read().strip()
        error = child.wait()

        if error != 0:
            raise Error("non-zero exitcode (%s) for command: %s\n\n%s" % 
                        (os.WEXITSTATUS(error), command, command_output))

        return command_output

