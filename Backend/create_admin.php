<?php
if (PHP_SAPI !== "cli") {
    http_response_code(404);
    exit;
}

$password = getenv("MEDPRED_ADMIN_PASSWORD");
if (!is_string($password) || strlen($password) < 8) {
    fwrite(STDERR, "Set MEDPRED_ADMIN_PASSWORD to a password of at least 8 characters before running this script.\n");
    exit(1);
}

require_once __DIR__ . "/db_config.php";

$conn->query(
    "CREATE TABLE IF NOT EXISTS admin_accounts (
        admin_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
);

$email = "admin@gmail.com";
$stmt = $conn->prepare("SELECT admin_id FROM admin_accounts WHERE email = ? LIMIT 1");
$stmt->bind_param("s", $email);
$stmt->execute();
$existingAdmin = $stmt->get_result()->fetch_assoc();
$stmt->close();

if ($existingAdmin) {
    fwrite(STDOUT, "The admin account already exists; its password was not changed.\n");
    exit(0);
}

$passwordHash = password_hash($password, PASSWORD_DEFAULT);
$stmt = $conn->prepare("INSERT INTO admin_accounts (email, password_hash) VALUES (?, ?)");
$stmt->bind_param("ss", $email, $passwordHash);
$stmt->execute();
$stmt->close();

fwrite(STDOUT, "Admin account created for " . $email . ".\n");
