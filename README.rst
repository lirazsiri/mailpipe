Usage
=====

mailpipe-post
-------------

Parse a mail post and pipe through to a command action.

Options::

    --mailback-output                  Mail action output back to sender
    --mailback-error                   Mail action errors back to sender
    --bodyfilter filter-command        Pass body through filter-command
                                       (triggers error if exitcode != 0)

Action command interface::
    
    (echo title; cat body) | action urlencode(sender_email)

mailpipe-reply
--------------

Invoke an action from a parsed mail reply. Useful for handling a reply
to an automatic notification from a website (for example).

Options::

    --mailback-error                   Mail action errors back to sender
    --bodyfilter filter-command        Pass body through filter-command
                                       (triggers error if exitcode != 0)

    --quoted-firstline-re='REGEXP'     Regexp for first line of quoted text
                                       Default: $DEFAULT_QUOTED_FIRSTLINE_RE

    --quoted-actiontoken-re='REGEXP'   Regexp for action token in qouted text
                                       Default: $DEFAULT_QUOTED_ACTIONTOKEN_RE

    --auth-sender=SECRET | PATH        Authenticate sender with secret
                                       Accepts a string value or a file path

Action command interface::
    
    (echo title; cat body) | action urlencode(sender_email) action_token

Example setup::

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


mailpipe-cli
------------

Invoke a cli command from an e-mail

Options::

    -t --timeout=SECONDS   How many seconds before command times out (default: %d)

Example usage::

    cat path/to/test.eml | mail2cli echo "arguments: " | sendmail -t

mailpipe-debug
--------------

Mailpipe debug tool traps execution context for inspection

Environment variables::

    MAILPIPE_TMPDIR         Path where we save debug data
                            Default: /tmp/mailpipe-debug

Context data::

    $MAILPIPE_TMPDIR/<id>/  Per-run location where context is saved
        rerun               Symlink to executable that reruns context

        id                  <uid>:<gid>:<groups>
        env                 Serialized environment

        command             Command executed through mailpipe-debug
        exitcode            Exitcode of executed command

        stdin               Input data passed though mailpipe
        stdout              Saved output from the executed command
        stderr              Saved error output from the executed command

Example usage::

    # capture execution context
    cat > $HOME/.forward << 'EOF'
    "| mailpipe-debug"
    EOF

    # wraps around command transparently
    cat > $HOME/.forward << 'EOF'
    "| PATH=$HOME/bin:$PATH mailpipe-reply --mail-error post_comment.php"
    EOF


