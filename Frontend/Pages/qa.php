<?php
session_start();

if (!isset($_SESSION["user_id"])) {
    header("Location: login.php");
    exit;
}

$user_id = (int) $_SESSION["user_id"];
$uploadSuccess = $_SESSION["upload_success"] ?? null;
if (strtolower($_SERVER["HTTP_X_REQUESTED_WITH"] ?? "") !== "xmlhttprequest") {
    unset($_SESSION["upload_success"]);
}

require_once __DIR__ . "/../../Backend/db_config.php";

// Allowed dropdown values (used for the form and for validation)
//$smoking_options = ["Never", "Former", "Current"];
$smoking_options = ['Never','No Info','Current','Former','Ever','Not current'];
$alcohol_options = ["None", "Occasional", "Moderate", "Heavy"];

// Page to go to after the questionnaire is saved (change this to your next page)
$next_page = "res.php";

$message = "";
$error   = "";

// ---------- Handle form submit (insert or update) ----------
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $smoking = $_POST["smoking_status"] ?? "";
    $alcohol = $_POST["alcohol_consumption"] ?? "";
    $dm       = isset($_POST["dm"]) ? 1 : 0;
    $htn      = isset($_POST["htn"]) ? 1 : 0;
    $fh_heart = 0;
    $h_feet   = $_POST["height_feet"] ?? "";
    $h_inches = $_POST["height_inches"] ?? "0";
    $weight   = $_POST["weight_kg"] ?? "";

    if (
        !in_array($smoking, $smoking_options, true) ||
        !in_array($alcohol, $alcohol_options, true)
    ) {
        $error = "Please select valid options.";
    } elseif (!is_numeric($h_feet) || !is_numeric($h_inches) || !is_numeric($weight)
              || $h_feet < 3 || $h_feet > 8 || $h_inches < 0 || $h_inches >= 12
              || $weight < 10 || $weight > 300) {
        $error = "Please enter a valid height (3-8 ft, 0-11 in) and weight (10-300 kg).";
    } else {
        // Convert to metric and calculate BMI = kg / (m * m)
        $total_inches = ((float) $h_feet * 12) + (float) $h_inches;
        $height_ft = round($total_inches / 12, 2);   // height stored in feet
        $weight_kg = round((float) $weight, 2);
        $height_m = $total_inches * 0.0254;
        $bmi = round($weight_kg / ($height_m * $height_m), 2);

        // Does this user already have a record?
        $stmt = mysqli_prepare($conn, "SELECT questionnaire_id FROM health_questionnaires WHERE user_id = ? LIMIT 1");
        mysqli_stmt_bind_param($stmt, "i", $user_id);
        mysqli_stmt_execute($stmt);
        $res = mysqli_stmt_get_result($stmt);
        $existing = mysqli_fetch_assoc($res);
        mysqli_stmt_close($stmt);

        if ($existing) {
            $stmt = mysqli_prepare($conn,
                "UPDATE health_questionnaires
                        SET smoking_status = ?, alcohol_consumption = ?, dm = ?, htn = ?,
                            height_ft = ?, weight_kg = ?, bmi = ?
                      WHERE user_id = ?");
                mysqli_stmt_bind_param($stmt, "ssiidddi", $smoking, $alcohol, $dm, $htn, $height_ft, $weight_kg, $bmi, $user_id);
            $message = "Your details have been updated.";
        } else {
            $stmt = mysqli_prepare($conn,
                "INSERT INTO health_questionnaires
                    (user_id, smoking_status, alcohol_consumption,
                     dm, htn, family_history_heart_disease,
                     height_ft, weight_kg, bmi, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())");
            mysqli_stmt_bind_param($stmt, "issiiiddd", $user_id, $smoking, $alcohol, $dm, $htn, $fh_heart, $height_ft, $weight_kg, $bmi);
            $message = "Your details have been saved.";
        }
        mysqli_stmt_execute($stmt);
        mysqli_stmt_close($stmt);
    }
}

// ---------- Load saved data (to pre-fill the form) ----------
$data = [
    "smoking_status"               => "",
    "alcohol_consumption"          => "",
    "dm"                           => 0,
    "htn"                          => 0,
    "height_ft"                    => null,
    "weight_kg"                    => null,
    "bmi"                          => null,
];
$has_record = false;

$stmt = mysqli_prepare($conn,
    "SELECT smoking_status, alcohol_consumption, dm, htn,
            height_ft, weight_kg, bmi
       FROM health_questionnaires WHERE user_id = ? LIMIT 1");
mysqli_stmt_bind_param($stmt, "i", $user_id);
mysqli_stmt_execute($stmt);
$res = mysqli_stmt_get_result($stmt);
if ($row = mysqli_fetch_assoc($res)) {
    $data = $row;
    $has_record = true;
}
mysqli_stmt_close($stmt);

// Split stored decimal feet back into feet + inches for the form
$pre_feet = $pre_inches = "";
if ($data["height_ft"] !== null) {
    $total_in   = (int) round($data["height_ft"] * 12);
    $pre_feet   = intdiv($total_in, 12);
    $pre_inches = $total_in % 12;
}

function h($v) { return htmlspecialchars((string) $v, ENT_QUOTES, "UTF-8"); }
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#f4f8f7">
    <title>Health questionnaire | MedPredict</title>
    <link rel="stylesheet" href="../CSS/qa.css">
</head>
<body>
<header class="questionnaire-topbar">
    <a class="brand" href="home.php"><span class="brand-mark">M</span> MedPredict</a>
    <a class="topbar-link" href="home.php">Back to dashboard <span aria-hidden="true">→</span></a>
</header>
<main class="questionnaire-shell">
    <div class="questionnaire-intro">
        <p class="eyebrow">YOUR HEALTH OVERVIEW</p>
        <h1>A little more about you</h1>
        <p>These details help provide context for your health information. Your saved answers can be updated any time.</p>
    </div>
<div class="card" id="questionnaire-card">
    <div class="card-heading">
        <span class="section-number">01</span>
        <div><h2 class="card-title" id="form-title">Health questionnaire</h2><p>All fields are used to build your personal overview.</p></div>
    </div>

    <?php if (is_string($uploadSuccess) && $uploadSuccess !== ""): ?><div class="msg ok" id="upload-success-msg" role="status" aria-live="polite"><?= h($uploadSuccess) ?></div><?php endif; ?>
    <?php if ($message): ?><div class="msg ok" id="success-msg"><?= h($message) ?></div><?php endif; ?>
    <?php if ($error): ?><div class="msg err" id="error-msg"><?= h($error) ?></div><?php endif; ?>

    <form method="post" action="" id="health-form" class="health-form">

        <div class="form-group" id="group-smoking">
            <label for="smoking_status">Smoking status</label>
            <select name="smoking_status" id="smoking_status" class="form-select" required>
                <option value="" disabled <?= $data["smoking_status"] === "" ? "selected" : "" ?>>Select...</option>
                <?php foreach ($smoking_options as $opt): ?>
                    <option value="<?= h($opt) ?>" <?= $data["smoking_status"] === $opt ? "selected" : "" ?>><?= h($opt) ?></option>
                <?php endforeach; ?>
            </select>
        </div>

        <div class="form-group" id="group-alcohol">
            <label for="alcohol_consumption">Alcohol consumption</label>
            <select name="alcohol_consumption" id="alcohol_consumption" class="form-select" required>
                <option value="" disabled <?= $data["alcohol_consumption"] === "" ? "selected" : "" ?>>Select...</option>
                <?php foreach ($alcohol_options as $opt): ?>
                    <option value="<?= h($opt) ?>" <?= $data["alcohol_consumption"] === $opt ? "selected" : "" ?>><?= h($opt) ?></option>
                <?php endforeach; ?>
            </select>
        </div>

        <div class="form-group" id="group-height">
            <label for="height_feet">Height</label>
            <div class="input-row" id="height-row">
                <div class="input-wrap">
                    <input type="number" name="height_feet" id="height_feet" class="form-input"
                           min="3" max="8" step="1" placeholder="Feet"
                           value="<?= h($pre_feet) ?>" required>
                    <span class="input-unit">ft</span>
                </div>
                <div class="input-wrap">
                    <input type="number" name="height_inches" id="height_inches" class="form-input"
                           min="0" max="11" step="0.1" placeholder="Inches"
                           value="<?= h($pre_inches) ?>" required>
                    <span class="input-unit">in</span>
                </div>
            </div>
        </div>

        <div class="form-group" id="group-weight">
            <label for="weight_kg">Weight</label>
            <div class="input-wrap">
                <input type="number" name="weight_kg" id="weight_kg" class="form-input"
                       min="10" max="300" step="0.1" placeholder="e.g. 68.5"
                       value="<?= h($data["weight_kg"]) ?>" required>
                <span class="input-unit">kg</span>
            </div>
        </div>

        <?php if ($data["bmi"] !== null): ?>
            <div class="bmi-box" id="bmi-box">
                <span class="bmi-label">Your BMI</span>
                <span class="bmi-value" id="bmi-value"><?= h($data["bmi"]) ?></span>
            </div>
        <?php endif; ?>

        <div class="form-group" id="group-background">
            <span class="group-label">Patient background</span>
            <p>Do you have hypertension or diabetes?</p>
            <label class="check" for="dm">
                <input type="checkbox" name="dm" id="dm" value="1" <?= $data["dm"] ? "checked" : "" ?>>
                I have Heart Disease
            </label>
            <label class="check" for="htn">
                <input type="checkbox" name="htn" id="htn" value="1" <?= $data["htn"] ? "checked" : "" ?>>
                I have hypertension
            </label>
        </div>

        <button type="submit" id="save-btn" class="btn-submit"><?= $has_record ? "Update Details" : "Save Details" ?></button>
    </form>

    <?php if ($has_record): ?>
        <a class="next-btn" id="next-btn" href="<?= h($next_page) ?>">Next &rarr;</a>
    <?php endif; ?>
</div>
</main>
<dialog class="prediction-dialog" id="predictionDialog" aria-labelledby="predictionDialogTitle" aria-describedby="predictionStatus" aria-busy="true">
    <div class="prediction-dialog-content">
        <span class="prediction-spinner" aria-hidden="true"></span>
        <p class="prediction-kicker">PREDICTION IN PROGRESS</p>
        <h2 id="predictionDialogTitle">Preparing your results</h2>
        <p id="predictionStatus" role="status" aria-live="polite">Running your details through our trained prediction models.</p>
    </div>
</dialog>
<script src="../script/qa.js"></script>
</body>
</html>         
