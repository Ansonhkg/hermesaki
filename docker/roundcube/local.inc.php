<?php
$config['imap_conn_options'] = ['ssl' => ['verify_peer' => true, 'verify_peer_name' => true, 'cafile' => '/etc/hermesaki/ca.pem']];
$config['smtp_conn_options'] = $config['imap_conn_options'];
$config['product_name'] = 'Hermesaki';
$config['login_autocomplete'] = 0;
