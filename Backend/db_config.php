<?php
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

$configPath = __DIR__ . '/config.local.php';
if (!is_file($configPath)) {
    throw new RuntimeException('Missing Backend/config.local.php. Copy config.local.example.php and fill in your hosting values.');
}
$config = require $configPath;

$host = trim((string)($config['db_host'] ?? ''));
$user = trim((string)($config['db_user'] ?? ''));
$pass = (string)($config['db_password'] ?? '');
$db   = trim((string)($config['db_name'] ?? ''));

if ($host === '' || $user === '' || $db === '' || $pass === '') {
    throw new RuntimeException('Database configuration is incomplete. Check Backend/config.local.php.');
}

$conn = mysqli_connect($host, $user, $pass, $db);
mysqli_set_charset($conn, 'utf8mb4');
