<?php
include 'db_config.php';

$user_stmt = $conn->prepare(
    "SELECT date_of_birth, sex FROM users WHERE user_id = ? LIMIT 1"
);
$user_stmt->bind_param("i", $user_id);
$user_stmt->execute();
$user = $user_stmt->get_result()->fetch_assoc();
$user_stmt->close();

if (!$user || !isset($user["date_of_birth"], $user["sex"])) {
    throw new RuntimeException("Could not load the user's date of birth and gender.");
}

$storedGender = strtolower(trim((string) $user["sex"]));
if ($storedGender === "1" || $storedGender === "male") {
    $gender = 1;
} elseif ($storedGender === "0" || $storedGender === "female") {
    $gender = 0;
} else {
    throw new RuntimeException("The user's gender is invalid.");
}

$dateOfBirth = DateTimeImmutable::createFromFormat("!Y-m-d", $user["date_of_birth"]);
$dateErrors = DateTimeImmutable::getLastErrors();
if (
    !$dateOfBirth ||
    ($dateErrors !== false && ($dateErrors["warning_count"] > 0 || $dateErrors["error_count"] > 0)) ||
    $dateOfBirth > new DateTimeImmutable("today")
) {
    throw new RuntimeException("The user's date of birth is invalid.");
}

$age = $dateOfBirth->diff(new DateTimeImmutable("today"))->y;
$report_stmt = $conn->prepare("INSERT INTO blood_reports (user_id) VALUES (?)");
$report_stmt->bind_param("i", $user_id);

if ($report_stmt->execute()) {
    $report_id = $conn->insert_id;
    $report_stmt->close();

    $par = "";
    $val = "";

    $result_stmt = $conn->prepare(
        "INSERT INTO blood_test_results (`report_id`, `age`, `gender`) VALUES (?, ?, ?)"
    );
    $result_stmt->bind_param("iii", $report_id, $age, $gender);
    $result_stmt->execute();
    $result_stmt->close();
    $insert_res_id = $conn->insert_id;

    $conn->query(
        "CREATE TABLE IF NOT EXISTS blood_test_observations (
            observation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            result_id INT NOT NULL,
            test_name VARCHAR(64) NOT NULL,
            result_value TEXT NOT NULL,
            INDEX (result_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    );

    $assignments = [];
    $values = [];
    $observation_stmt = $conn->prepare(
        "INSERT INTO blood_test_observations (result_id, test_name, result_value) VALUES (?, ?, ?)"
    );
    foreach($features as $feature){
        $key = $feature["test_name"];
        $res = $feature["result"];

        if (!is_string($key) || !preg_match('/\A[a-zA-Z_][a-zA-Z0-9_]*\z/', $key)) {
            throw new RuntimeException("Invalid test result column.");
        }
        if (!is_scalar($res)) {
            throw new RuntimeException("Invalid test result value for " . $key . ".");
        }
        $res = (string) $res;
        $observation_stmt->bind_param("iss", $insert_res_id, $key, $res);
        $observation_stmt->execute();

        if (is_numeric($res)) {
            $assignments[] = "`" . $key . "` = ?";
            $values[] = $res;
        }
    }
    $observation_stmt->close();

    if (!empty($assignments)) {
        $insert_val = "UPDATE blood_test_results SET " . implode(", ", $assignments) .
                  " WHERE `result_id` = ?";
        $stmt = $conn->prepare($insert_val);
        $types = str_repeat("s", count($values)) . "i";
        $values[] = $insert_res_id;
        $bind_params = [$types];
        foreach ($values as &$value) {
            $bind_params[] = &$value;
        }
        call_user_func_array([$stmt, "bind_param"], $bind_params);
        $stmt->execute();
        $stmt->close();
    }
    $_SESSION["report_id"]=$insert_res_id;
} else {
    $report_stmt->close();
    throw new RuntimeException("Could not save the blood report.");
}
?>