from subprocess import *

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

