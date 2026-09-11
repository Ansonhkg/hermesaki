<?php
// Exercise the real pinned dependencies, including SMTP's legacy PEAR includes.
// Both initialization orders must work; no server or credentials are needed.
require '/usr/src/roundcubemail/vendor/autoload.php';
if (($argv[1] ?? '') === 'host-first') {
    class_exists('PEAR');
}
require '/usr/src/roundcubemail/plugins/mcpcube/mcpcube.php';
new Net_SMTP();
new Mail_mime();
new PhpParser\ParserFactory();
foreach (['PEAR', 'Net_SMTP', 'Mail_mime'] as $class) {
    $file = (new ReflectionClass($class))->getFileName();
    if (str_contains($file, '/plugins/mcpcube/')) {
        throw new RuntimeException("Plugin shadowed host dependency: $class");
    }
}
echo "Roundcube SMTP, MIME and MCP dependencies coexist\n";
