
<?php
session_start();

if (!isset($_SESSION["user_id"])) {
    header("Location: login.php");
    exit;
}

$uploadError = $_SESSION["upload_error"] ?? null;
unset($_SESSION["upload_error"]);
$userName = trim((string) ($_SESSION["full_name"] ?? ""));
if ($userName === "") {
    $userName = "there";
}
?>


<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#f4f8f7">
    <meta name="description" content="Upload a blood report and explore a clear, structured health overview with MedPredict.">
    <title>MedPredict | Health overview</title>

    <link rel="stylesheet" href="../CSS/home.css">
</head>
<body>
     <nav>
        <a class="brand" href="home.php"><span class="brand-mark">M</span> MedPredict</a>

        <div>
            <span class="nav-greeting">Hi, <?= htmlspecialchars($userName, ENT_QUOTES, "UTF-8") ?></span>
            <a href="home.php">Home</a>
            <a href="#diseases">Diseases</a>
            <a href="#about">About</a>
            <a class="nav-logout" href="logout.php">Log out</a>
        </div>
    </nav>

    <section class="hero">

        <div class="hero-text">
            <p class="eyebrow"><span></span> WELCOME BACK, <?= htmlspecialchars($userName, ENT_QUOTES, "UTF-8") ?></p>
            <h1>Multiple Disease<br>
                <span>Prediction System</span>
            </h1>

            <p>
                Turn your blood report into a clear, structured overview.
                Understand your health data with a little more confidence.
            </p>

            <div class="box">
                <div class="upload-icon" aria-hidden="true">↑</div>
                <div class="upload-copy">
                    <span class="upload-kicker">START WITH YOUR REPORT</span>
                    <h2>Upload a blood report</h2>
                    <p>Choose a PDF report to extract and review its lab values.</p>
                </div>

                <?php if (is_string($uploadError) && $uploadError !== ""): ?>
                    <div class="upload-error" role="alert" aria-live="assertive">
                        <strong>We couldn't use this report</strong>
                        <p><?= htmlspecialchars($uploadError, ENT_QUOTES, "UTF-8") ?></p>
                    </div>
                <?php endif; ?>

                <form action="../../Backend/upload.php" method="POST" enctype="multipart/form-data" id="uploadForm">
                    <label class="file-picker" for="bloodReport">
                        <span class="file-picker-icon" aria-hidden="true">＋</span>
                        <span><strong>Choose a PDF</strong><small>PDF format · max 25 MB</small></span>
                        <input id="bloodReport" type="file" name="pdf" accept=".pdf,application/pdf" required>
                    </label>
                    <button class="btn-box" type="submit" id="uploadButton">Continue with report</button>
                </form>

                <p id="fileName" aria-live="polite"></p>
                <p class="privacy-note"><span aria-hidden="true">●</span> Your report is handled securely.</p>
            </div>
        </div>

    </section>

    <dialog class="upload-dialog" id="uploadStatus" aria-labelledby="uploadDialogTitle" aria-describedby="uploadStatusMessage" aria-busy="false">
        <div class="upload-dialog-content">
            <span class="loading-spinner" aria-hidden="true"></span>
            <p class="upload-kicker">REPORT PROCESSING</p>
            <h2 id="uploadDialogTitle">Extracting your lab results</h2>
            <p id="uploadStatusMessage" aria-live="polite">Uploading your PDF and extracting lab parameters. This may take a moment.</p>
            <button type="button" class="upload-dialog-close" id="uploadDialogClose" hidden>Close</button>
        </div>
    </dialog>

    <section id="diseases" class="disease-section">
        <div class="section-heading">
            <p class="eyebrow">A MORE INFORMED YOU</p>
            <h2>Health areas in focus</h2>
            <p>Explore the health categories represented in the MedPredict experience.</p>
        </div>

        <div class="cards">

            <div class="card">
                <span class="card-icon icon-coral" aria-hidden="true">✚</span>
                <h3>Diabetes</h3>
                <p>Explore factors associated with blood sugar health.</p>
            </div>

            <div class="card">
                <span class="card-icon icon-teal" aria-hidden="true">⌁</span>
                <h3>Liver Disease</h3>
                <p>Review liver-related markers from your lab report.</p>
            </div>

            <div class="card">
                <span class="card-icon icon-blue" aria-hidden="true">◈</span>
                <h3>Kidney Disease</h3>
                <p>Explore kidney health information and indicators.</p>
            </div>

        </div>
    </section>

    <section id="about" class="about-section">
        <div class="section-heading">
            <p class="eyebrow">SIMPLE BY DESIGN</p>
            <h2>From report to understanding</h2>
            <p>A straightforward path helps keep your health information easy to follow.</p>
        </div>
        <div class="steps">
            <article class="step"><span>01</span><div><h3>Upload</h3><p>Choose your blood report in PDF format.</p></div></article>
            <article class="step"><span>02</span><div><h3>Review</h3><p>Check the extracted values and complete your health details.</p></div></article>
            <article class="step"><span>03</span><div><h3>Understand</h3><p>View a structured summary of the available results.</p></div></article>
        </div>
    </section>

    <!-- <footer><span>© 2026 MedPredict</span><span>Health information, made easier to understand.</span></footer> -->
    <script src="../script/home.js"></script>

</body>
</html>