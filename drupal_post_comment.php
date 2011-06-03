#!/usr/bin/php
<?php

exit(main($GLOBALS['argv']));

function mail2uid($mail) {
    return db_result(db_query("SELECT uid FROM {users} WHERE LOWER(mail) = LOWER('%s')", $mail));
}


function post_comment($path, $user_mail, $subject, $comment) {
	chdir("/usr/share/drupal6");

	require_once './includes/bootstrap.inc';
	drupal_bootstrap(DRUPAL_BOOTSTRAP_FULL);

    $uid = mail2uid($user_mail);
    if(!$uid)
		throw new Exception("no such user {$user_mail}");

	$pid = NULL;
	if(preg_match('/(.*)#comment-(\d+)/', $path, $m)) {
		$path = $m[1];
		$pid = $m[2];
	}

	$path = drupal_get_normal_path($path);
	if(!preg_match('|node/(\d+)$|', $path, $m))
		throw new Exception("can't lookup nid for path=$path");
	
	$nid = $m[1];
	$comment = array(
		'uid' => $uid,
		'nid' => $nid,
		'pid' => $pid,
		'subject' => $subject,
		'comment' => $comment
	);

    _comment_form_submit($comment); // e.g., fix empty subject
	comment_save($comment);
}

function main($args) {

	if(count($args) != 3) {
		print "Syntax: {$args[0]} path[#comment-\$cid] user-mail\n\n";
		print "Example usage:\n\n";
		print "    (echo 'comment title'; cat comment_body.txt) | {$args[0]} blog/great-post#comment-1234 2\n";
		exit(1);
	}

	$url = $args[1];
    $user_mail = $args[2];

	/* get comment from stdin */
	$fh = fopen("php://stdin", "r");

	$subject = fgets($fh);
	$comment = stream_get_contents($fh);

	post_comment($url, $user_mail, $subject, $comment);
	return 0;
}



?>
