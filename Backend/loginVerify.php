
<?php
session_start();
include "db_config.php";

if (isset($_POST["loginNew"])) {

    $email = trim($_POST["email_login"] ?? "");
    $password = $_POST["loginPassword"] ?? "";


    // Find user by email
    $sql = "SELECT user_id, full_name, email, password_hash
            FROM users
            WHERE email = ?";

    $stmt = $conn->prepare($sql);
    $stmt->bind_param("s", $email);
    $stmt->execute();

    $result = $stmt->get_result();

    if ($result->num_rows === 1) {

        $user = $result->fetch_assoc();

        // Verify password
        if (password_verify($password, $user["password_hash"])) {

            // Prevent session fixation
            session_regenerate_id(true);

            // Create session variables
            $_SESSION["user_id"] = $user["user_id"];
            $_SESSION["full_name"] = $user["full_name"];
            $_SESSION["email"] = $user["email"];

            $stmt->close();
            $conn->close();

            // Redirect to home page
            header("Location: ../Frontend/pages/home.php");
            exit;

        } else {
            echo "<script>alert('Invalid email or password'); window.history.back();</script>";
            exit;
        }

    } else {
        echo "<script>alert('Invalid email or password'); window.history.back();</script>";
        exit;
    }

    $stmt->close();
    $conn->close();
}
?>
