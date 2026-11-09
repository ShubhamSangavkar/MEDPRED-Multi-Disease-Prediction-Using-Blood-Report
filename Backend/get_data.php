<?php
if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
require_once __DIR__ . "/db_config.php";
mysqli_set_charset($conn, "utf8mb4");

$data = null;
$qa_data = null;
$reportId = filter_var($_SESSION["report_id"] ?? null, FILTER_VALIDATE_INT);
$userId = filter_var($_SESSION["user_id"] ?? null, FILTER_VALIDATE_INT);

if ($reportId && $userId) {
    $stmt = $conn->prepare(
        "SELECT results.*
           FROM blood_test_results AS results
           INNER JOIN blood_reports AS reports ON reports.report_id = results.report_id
          WHERE results.result_id = ? AND reports.user_id = ?
          LIMIT 1"
    );
    $stmt->bind_param("ii", $reportId, $userId);
    $stmt->execute();
    $data = $stmt->get_result()->fetch_assoc();
    $stmt->close();

    $stmt = $conn->prepare(
        "SELECT * FROM health_questionnaires WHERE user_id = ? LIMIT 1"
    );
    $stmt->bind_param("i", $userId);
    $stmt->execute();
    $qa_data = $stmt->get_result()->fetch_assoc();
    $stmt->close();
}
?>