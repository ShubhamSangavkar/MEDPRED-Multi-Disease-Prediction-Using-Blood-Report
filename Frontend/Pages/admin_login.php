<?php
session_start();

if (isset($_SESSION["admin_id"])) {
    header("Location: admin.php");
    exit;
}

if (!isset($_SESSION["admin_login_csrf"])) {
    $_SESSION["admin_login_csrf"] = bin2hex(random_bytes(32));
}

$error = "";
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $csrfToken = $_POST["csrf_token"] ?? "";
    if (!is_string($csrfToken) || !hash_equals($_SESSION["admin_login_csrf"], $csrfToken)) {
        http_response_code(400);
        $error = "Your sign-in session expired. Reload the page and try again.";
    } else {
        try {
            require_once __DIR__ . "/../../Backend/db_config.php";
            $email = strtolower(trim((string) ($_POST["email"] ?? "")));
            $password = $_POST["password"] ?? "";
            $stmt = $conn->prepare(
                "SELECT admin_id, email, password_hash FROM admin_accounts WHERE email = ? LIMIT 1"
            );
            $stmt->bind_param("s", $email);
            $stmt->execute();
            $admin = $stmt->get_result()->fetch_assoc();
            $stmt->close();

            if (
                is_array($admin) &&
                is_string($password) &&
                password_verify($password, $admin["password_hash"])
            ) {
                session_regenerate_id(true);
                $_SESSION["admin_id"] = (int) $admin["admin_id"];
                $_SESSION["admin_email"] = $admin["email"];
                unset($_SESSION["admin_login_csrf"]);
                header("Location: admin.php");
                exit;
            }

            $error = "Invalid email or password.";
        } catch (Throwable $exception) {
            error_log("Admin sign-in failed: " . $exception->getMessage());
            http_response_code(500);
            $error = "Admin sign-in is unavailable right now. Please try again later.";
        }
    }
}

function h($value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES, "UTF-8");
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Sign In | MedPredict</title>
    <link rel="stylesheet" href="../CSS/admin.css">
</head>
<body>
    <main class="auth-shell">
        <section class="auth-card" aria-labelledby="admin-title">
            <a class="brand" href="login.php"><span class="brand-mark">M</span> MedPredict</a>
            <p class="eyebrow">ADMINISTRATION</p>
            <h1 id="admin-title">Admin sign in</h1>
            <p class="intro">Sign in to review site activity and prediction records.</p>
            <?php if ($error): ?>
                <p class="form-error" role="alert"><?= h($error) ?></p>
            <?php endif; ?>
            <form method="post" action="admin_login.php">
                <input type="hidden" name="csrf_token" value="<?= h($_SESSION["admin_login_csrf"]) ?>">
                <label for="email">Admin email</label>
                <input id="email" name="email" type="email" value="admin@gmail.com" autocomplete="username" required>
                <label for="password">Password</label>
                <input id="password" name="password" type="password" autocomplete="current-password" required>
                <button class="btn" type="submit">Sign in</button>
            </form>
            <a class="back-link" href="login.php">Return to MedPredict</a>
        </section>
    </main>
</body>
</html>
