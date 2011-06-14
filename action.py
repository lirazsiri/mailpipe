import os
import urllib

from commands import mkarg
from filter import FilterCommand
from popen2 import Popen4

class Error(Exception):
    pass

class Action:
    def __init__(self, action_command, bodyfilter=None):
        self.action_command = action_command
        self.bodyfilter = bodyfilter

    def parse_msg(self, msg):
        return msg['subject'], msg.get_payload()

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

