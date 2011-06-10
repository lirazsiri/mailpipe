import os
from subprocess import *
from email.mime.text import MIMEText

class Error(Exception):
    pass

def sendmail(sender, recipient, subject, body):
    email = MIMEText(body)
    email['From'] = sender
    email['To'] = recipient
    email['Subject'] = subject

    if os.system("which sendmail > /dev/null") != 0:
        os.environ['PATH'] += ':/usr/local/sbin:/usr/sbin'

    child = Popen("sendmail -t", shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)

    stdout, stderr = None, None
    try:
        stdout, stderr = child.communicate(str(email))
    except OSError:
        pass

    returncode = child.wait()
    if stderr is None:
        stderr = child.stderr.read()

    if returncode != 0:
        errmsg = "sendmail error (%d)" % returncode
        if stderr:
            errmsg += ": " + stderr

        raise Error(errmsg)
