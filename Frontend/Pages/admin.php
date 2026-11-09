<?php
session_start();

if (!isset($_SESSION["admin_id"])) {
    header("Location: admin_login.php");
    exit;
}

if (!isset($_SESSION["admin_csrf"])) {
    $_SESSION["admin_csrf"] = bin2hex(random_bytes(32));
}

if ($_SERVER["REQUEST_METHOD"] === "POST" && ($_POST["action"] ?? "") === "logout") {
    $csrfToken = $_POST["csrf_token"] ?? "";
    if (!is_string($csrfToken) || !hash_equals($_SESSION["admin_csrf"], $csrfToken)) {
        http_response_code(400);
        exit("Invalid request token.");
    }

    unset($_SESSION["admin_id"], $_SESSION["admin_email"], $_SESSION["admin_csrf"]);
    session_regenerate_id(true);
    header("Location: admin_login.php");
    exit;
}

require_once __DIR__ . "/../../Backend/db_config.php";

$stats = ["users" => 0, "reports" => 0, "predictions" => 0];
$recentPredictions = [];
$dashboardError = "";

try {
    $stats["users"] = (int) $conn->query("SELECT COUNT(*) AS total FROM users")->fetch_assoc()["total"];
    $stats["reports"] = (int) $conn->query("SELECT COUNT(*) AS total FROM blood_reports")->fetch_assoc()["total"];

    $predictionTable = $conn->query("SHOW TABLES LIKE 'prediction_results'");
    if ($predictionTable->num_rows > 0) {
        $stats["predictions"] = (int) $conn->query(
            "SELECT COUNT(*) AS total FROM prediction_results"
        )->fetch_assoc()["total"];

        $result = $conn->query(
            "SELECT users.full_name, users.email, reports.report_id,
                    predictions.model_name, predictions.predicted_class,
                    predictions.class_probabilities, predictions.created_at
               FROM prediction_results AS predictions
               INNER JOIN blood_test_results AS results ON results.result_id = predictions.result_id
               INNER JOIN blood_reports AS reports ON reports.report_id = results.report_id
               INNER JOIN users ON users.user_id = reports.user_id
              ORDER BY predictions.created_at DESC
              LIMIT 20"
        );
        while ($row = $result->fetch_assoc()) {
            $recentPredictions[] = $row;
        }
        $result->free();
    }
} catch (Throwable $exception) {
    error_log("Could not load admin dashboard: " . $exception->getMessage());
    $dashboardError = "Some dashboard data could not be loaded. Please try again later.";
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
    <title>Admin Dashboard | MedPredict</title>
    <link rel="stylesheet" href="../CSS/admin.css">
</head>
<body>
    <nav class="topbar">
        <a class="brand" href="admin.php"><span class="brand-mark">M</span> MedPredict <span class="admin-label">Admin</span></a>
        <form method="post" action="admin.php">
            <input type="hidden" name="action" value="logout">
            <input type="hidden" name="csrf_token" value="<?= h($_SESSION["admin_csrf"]) ?>">
            <button class="logout-button" type="submit">Sign out</button>
        </form>
    </nav>
    <main class="dashboard">
        <header class="dashboard-heading">
            <div>
                <p class="eyebrow">SITE OVERVIEW</p>
                <h1>Admin dashboard</h1>
                <p class="intro">Signed in as <?= h($_SESSION["admin_email"] ?? "Administrator") ?>. Health information is confidential.</p>
            </div>
            <a class="back-link" href="home.php">Open website</a>
        </header>

        <?php if ($dashboardError): ?>
            <p class="form-error" role="alert"><?= h($dashboardError) ?></p>
        <?php endif; ?>

        <section class="stats-grid" aria-label="Website totals">
            <article class="stat-card"><span>Registered users</span><strong><?= number_format($stats["users"]) ?></strong></article>
            <article class="stat-card"><span>Uploaded reports</span><strong><?= number_format($stats["reports"]) ?></strong></article>
            <article class="stat-card"><span>Saved predictions</span><strong><?= number_format($stats["predictions"]) ?></strong></article>
        </section>

        <section class="records-card" aria-labelledby="recent-title">
            <div class="section-heading">
                <div>
                    <p class="eyebrow">LATEST ACTIVITY</p>
                    <h2 id="recent-title">Recent predictions</h2>
                </div>
                <span class="record-count">Up to 20 records</span>
            </div>
            <?php if (!$recentPredictions): ?>
                <p class="empty-state">No saved prediction records yet.</p>
            <?php else: ?>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th scope="col">Date</th>
                                <th scope="col">User</th>
                                <th scope="col">Report</th>
                                <th scope="col">Model</th>
                                <th scope="col">Result</th>
                                <th scope="col">Disease probability</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($recentPredictions as $record): ?>
                                <?php
                                $probabilities = json_decode($record["class_probabilities"], true);
                                $diseaseProbability = is_array($probabilities) ? ($probabilities["1"] ?? null) : null;
                                ?>
                                <tr>
                                    <td><?= h($record["created_at"]) ?></td>
                                    <td><strong><?= h($record["full_name"]) ?></strong><small><?= h($record["email"]) ?></small></td>
                                    <td>#<?= h($record["report_id"]) ?></td>
                                    <td><?= h(ucfirst($record["model_name"])) ?></td>
                                    <td><?= $record["predicted_class"] === "1" ? "Higher risk" : "Lower risk" ?></td>
                                    <td><?= is_numeric($diseaseProbability) ? h(number_format((float) $diseaseProbability * 100, 1)) . "%" : "—" ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </section>
    </main>
</body>
</html>
