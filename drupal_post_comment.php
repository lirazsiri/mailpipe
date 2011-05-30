#!/usr/bin/php
<?php

exit(main($GLOBALS['argv']));

function post_comment($path, $uid, $subject, $comment) {
	chdir("/usr/share/drupal6");

	require_once './includes/bootstrap.inc';
	drupal_bootstrap(DRUPAL_BOOTSTRAP_FULL);

	$pid = NULL;
	if(preg_match('/(.*)#comment-(\d+)/', $path, $m)) {
		$path = $m[1];
		$pid = $m[2];
	}

	$path = drupal_get_normal_path($path);
	if(!preg_match('|node/(\d+)$|', $path, $m)) {	
		throw new Exception("can't lookup nid for path=$path");
	}
	$nid = $m[1];
	$comment = array(
		'uid' => $uid,
		'nid' => $nid,
		'pid' => $pid,
		'subject' => $subject,
		'comment' => $comment
	);
	comment_save($comment);
}

function main($args) {

	if(count($args) != 3) {
		print "Syntax: {$args[0]} path[#comment-\$cid] uid\n\n";
		print "Example usage:\n\n";
		print "    (echo 'comment title'; cat comment_body.txt) | {$args[0]} blog/great-post#comment-1234 2\n";
		exit(1);
	}

	$url = $args[1];
	$uid = $args[2];

	/* get comment from stdin */
	$fh = fopen("php://stdin", "r");

	$subject = fgets($fh);
	$comment = stream_get_contents($fh);

	post_comment($url, $uid, $subject, $comment);
	return 0;
}



?>
