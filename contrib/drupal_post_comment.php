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

function post_comment($path, $user_mail, $subject, $comment) {
    global $base_url;
	chdir("/usr/share/drupal6");

	require_once './includes/bootstrap.inc';
	drupal_bootstrap(DRUPAL_BOOTSTRAP_FULL);

    $uid = mail2uid(get_sender_address($user_mail));
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
		'uid' => $uid ? $uid : 0,
		'nid' => $nid,
		'pid' => $pid,
		'subject' => $subject,
		'comment' => $comment
	);
    if($uid) {
        $user = user_load($uid);
        $comment['name'] = $user->name;
        $comment['mail'] = $user->mail;
    } else {
        if(preg_match('/^(.*?)\s*<(.*)>/', $user_mail, $match)) {
            $comment['name'] = $match[1];
            $comment['mail'] = $match[2];
        } else {
            $comment['mail'] = $user_mail;
        }
    }

    _comment_form_submit($comment); // e.g., fix empty subject
	comment_save($comment);
}

function main($args) {

	if(count($args) != 3) {
		print "Syntax: {$args[0]} path[#comment-\$cid] urlencoded(user-mail)\n\n";
		print "Example usage:\n\n";
		print "    (echo 'comment title'; cat comment_body.txt) | {$args[0]} blog/great-post#comment-1234 2\n";
		exit(1);
	}

    $user_mail = urldecode($args[1]);
	$url = $args[2];

	/* get comment from stdin */
	$fh = fopen("php://stdin", "r");

	$subject = rtrim(fgets($fh));
	$comment = stream_get_contents($fh);

	post_comment($url, $user_mail, $subject, $comment);
	return 0;
}



?>
