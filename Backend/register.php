<?php
include "db_config.php";

if (isset($_POST["registerNew"])) {

    $userName = trim($_POST['name'] ?? "");
    $mobile = trim($_POST["registerMobile"] ?? "");
    $gender = $_POST["Gender"] ?? null;
    $dob = $_POST["dob"] ?? "";
    $email = trim($_POST['email'] ?? "");
    $pass = $_POST["registerPassword"] ?? "";

    $dateOfBirth = is_string($dob) ? DateTimeImmutable::createFromFormat("!Y-m-d", $dob) : false;
    $dateErrors = DateTimeImmutable::getLastErrors();
    if (
        $userName === "" ||
        !in_array($gender, ["0", "1"], true) ||
        !$dateOfBirth ||
        ($dateErrors !== false && ($dateErrors["warning_count"] > 0 || $dateErrors["error_count"] > 0)) ||
        $dateOfBirth > new DateTimeImmutable("today")
    ) {
        http_response_code(400);
        exit("Please provide a valid name, gender, and date of birth.");
    }

    $hashedPassword = password_hash($pass, PASSWORD_DEFAULT);
    $gender = (int) $gender;

    $reg_user_query = "INSERT INTO users
    (full_name, email, password_hash, date_of_birth, sex, phone)
    VALUES (?, ?, ?, ?, ?, ?)";

    $stmt = $conn->prepare($reg_user_query);

    $stmt->bind_param(
        "ssssis",
        $userName,
        $email,
        $hashedPassword,
        $dob,
        $gender,
        $mobile
    );

    if ($stmt->execute()) {
        echo "<script>alert('Registration successful!');</script>";
        header("Location: ../Frontend/pages/login.php");
        exit();
    } else {
        echo "Registration failed.";
    }

    $stmt->close();
    $conn->close();

    


}


?>
