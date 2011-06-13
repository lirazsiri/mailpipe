#!/usr/bin/php
<?php

exit(main($GLOBALS['argv']));

function mail2uid($mail) {
    return db_result(db_query("SELECT uid FROM {users} WHERE LOWER(mail) = LOWER('%s')", $mail));
}

function get_sender_address($mail) {
    if(preg_match('/<(.*)>/', $mail, $match)) {
        return $match[1];
    }
    return $mail;
}

function post_node($type, $user_mail, $subject, $body) {
    global $base_url;

	chdir("/usr/share/drupal6");

	require_once './includes/bootstrap.inc';
	drupal_bootstrap(DRUPAL_BOOTSTRAP_FULL);

    $uid = mail2uid(get_sender_address($user_mail));
    if(!$uid)
		throw new Exception("no such user $user_mail");

    global $user;

    $orig_user = $user;
    $user = user_load($uid);

    if(!user_access("create $type content"))
        throw new Exception("{$user->mail} is not allowed to post $type type content");

    $form_state = array();
    module_load_include('inc', 'node', 'node.pages');
    $node = array('type' => $type);
    $form_state['values']['name'] = $user->name;
    $form_state['values']['title'] = $subject;
    $form_state['values']['body'] = $body;
    $form_state['values']['publish_on'] = 0;

    $form_state['values']['op'] = t('Save');
    drupal_execute("$type_node_form", $form_state, (object)$node);

    $nid = $form_state['nid'];

    $user = $orig_user;
    return url("node/$nid", array('absolute' => TRUE));
}

function main($args) {

	if(count($args) != 3) {
		print "Syntax: {$args[0]} type user@mail.address\n\n";
		print "Example usage:\n\n";
		print "    (echo 'comment title'; cat comment_body.txt) | {$args[0]} blog liraz@turnkeylinux.org\n";

		exit(1);
	}

    $type = $args[1];
    $user_mail = urldecode($args[2]);

	/* get comment from stdin */
	$fh = fopen("php://stdin", "r");

	$subject = rtrim(fgets($fh));
	$body = stream_get_contents($fh);

    try {
        $url = post_node($type, $user_mail, $subject, $body);
        print "$url\n";
    } catch(Exception $e) {
        print "error: {$e->getMessage()}\n";
        exit(1);
    }

	return 0;
}



?>
