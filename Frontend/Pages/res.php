<?php
session_start();

if (!isset($_SESSION["user_id"])) {
    header("Location: login.php");
    exit;
}

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

$reportId = filter_var($_SESSION["report_id"] ?? null, FILTER_VALIDATE_INT);
$userId = filter_var($_SESSION["user_id"], FILTER_VALIDATE_INT);
require_once __DIR__ . "/../../Backend/api_config.php";
require_once __DIR__ . "/../../Backend/api_config.php";
require_once __DIR__ . "/../../Backend/get_data.php";

$error = "";
$prediction = null;
$availableLiverLabCount = 0;

if (!$reportId || !$userId) {
    $error = "No report is available yet. Upload a blood report to see your results.";
} elseif (!$data) {
    $error = "We couldn't find this report. Please upload your report again.";
} else {
    $requiredLiverFields = ["age" => "age", "gender" => "gender"];
    $missingLiverFields = [];
    foreach ($requiredLiverFields as $field => $label) {
        if (!isset($data[$field]) || !is_numeric($data[$field])) {
            $missingLiverFields[] = $label;
        }
    }

    if ($missingLiverFields) {
        $error = "Liver prediction needs " . implode(", ", $missingLiverFields) .
            " in the blood report.";
    } else {
        $features = [
            "Age" => (int) $data["age"],
            "Gender" => (int) $data["gender"],
        ];
        $apiFieldNames = [
            "alb" => "ALB",
            "alkphos" => "Alkphos",
            "sgpt" => "Sgpt",
            "sgot" => "Sgot",
            "tb" => "TB",
            "tp" => "TP",
        ];
        foreach ($apiFieldNames as $databaseField => $apiField) {
            if (isset($data[$databaseField]) && is_numeric($data[$databaseField])) {
                $features[$apiField] = (float) $data[$databaseField];
                $availableLiverLabCount++;
            }
        }

        $curl = curl_init(medpredict_api_url("predict/liver"));
        curl_setopt_array($curl, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode($features),
            CURLOPT_HTTPHEADER => medpredict_api_headers(["Content-Type: application/json", "Accept: application/json"]),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 15,
        ]);

        $apiResponse = curl_exec($curl);
        $curlError = curl_error($curl);
        $statusCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
        curl_close($curl);

        if ($apiResponse === false) {
            $error = "The prediction service is unavailable right now. Please try again later.";
            error_log("Liver prediction request failed: " . $curlError);
        } elseif ($statusCode < 200 || $statusCode >= 300) {
            $error = "The prediction service couldn't process this report. Please try again later.";
            error_log("Liver prediction returned HTTP " . $statusCode . ": " . $apiResponse);
        } else {
            $prediction = json_decode($apiResponse, true);
            if (!is_array($prediction) || !isset($prediction["class_probabilities"]) ||
                !is_array($prediction["class_probabilities"])) {
                $prediction = null;
                $error = "The prediction service returned an unexpected response.";
                error_log("Liver prediction response had an unexpected format.");
            }
        }
    }
}

require_once __DIR__ . "/../../Backend/call_api/diabetes_results.php";
require_once __DIR__ . "/../../Backend/call_api/kidney_results.php";

$probabilities = [];
if ($prediction !== null) {
    foreach ($prediction["class_probabilities"] as $class => $probability) {
        if (is_numeric($probability) && (float) $probability >= 0 && (float) $probability <= 1) {
            $probabilities[(string) $class] = (float) $probability;
        }
    }
    if (!isset($probabilities["0"], $probabilities["1"])) {
        $error = "The prediction service did not return valid probabilities for both disease classes.";
        $prediction = null;
    }
}

$topClass = null;
if ($probabilities) {
    arsort($probabilities);
    $topClass = (string) array_key_first($probabilities);
}

$diabetesProbabilities = [];
if ($diabetesPrediction !== null) {
    foreach ($diabetesPrediction["class_probabilities"] as $class => $probability) {
        if (is_numeric($probability) && (float) $probability >= 0 && (float) $probability <= 1) {
            $diabetesProbabilities[(string) $class] = (float) $probability;
        }
    }
    if (!isset($diabetesProbabilities["0"], $diabetesProbabilities["1"])) {
        $diabetesError = "The diabetes prediction service did not return valid probabilities for both disease classes.";
        $diabetesPrediction = null;
    }
}

$diabetesTopClass = null;
if ($diabetesProbabilities) {
    arsort($diabetesProbabilities);
    $diabetesTopClass = (string) array_key_first($diabetesProbabilities);
}

$kidneyProbabilities = [];
if ($kidneyPrediction !== null) {
    foreach ($kidneyPrediction["class_probabilities"] as $class => $probability) {
        if (is_numeric($probability) && (float) $probability >= 0 && (float) $probability <= 1) {
            $kidneyProbabilities[(string) $class] = (float) $probability;
        }
    }
    if (!isset($kidneyProbabilities["0"], $kidneyProbabilities["1"])) {
        $kidneyError = "The kidney prediction service did not return valid probabilities for both disease classes.";
        $kidneyPrediction = null;
    }
}

$kidneyTopClass = null;
if ($kidneyProbabilities) {
    arsort($kidneyProbabilities);
    $kidneyTopClass = (string) array_key_first($kidneyProbabilities);
}

$predictionStorageError = "";
if ($reportId && $userId) {
    try {
        $conn->query(
            "CREATE TABLE IF NOT EXISTS prediction_results (
                prediction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                result_id INT NOT NULL,
                model_name VARCHAR(32) NOT NULL,
                predicted_class VARCHAR(16) NOT NULL,
                class_probabilities LONGTEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_result_model (result_id, model_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        );

        $savePrediction = function (string $modelName, ?string $predictedClass, array $classProbabilities) use ($conn, $reportId): void {
            if ($predictedClass === null) {
                return;
            }

            $probabilitiesJson = json_encode($classProbabilities, JSON_THROW_ON_ERROR);
            $stmt = $conn->prepare(
                "INSERT INTO prediction_results (result_id, model_name, predicted_class, class_probabilities)
                 VALUES (?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                    predicted_class = VALUES(predicted_class),
                    class_probabilities = VALUES(class_probabilities),
                    updated_at = CURRENT_TIMESTAMP"
            );
            $stmt->bind_param("isss", $reportId, $modelName, $predictedClass, $probabilitiesJson);
            $stmt->execute();
            $stmt->close();
        };

        $savePrediction("liver", $topClass, $probabilities);
        $savePrediction("diabetes", $diabetesTopClass, $diabetesProbabilities);
        $savePrediction("kidney", $kidneyTopClass, $kidneyProbabilities);
    } catch (Throwable $exception) {
        error_log("Could not save prediction results: " . $exception->getMessage());
        $predictionStorageError = "Your prediction is ready, but it couldn't be saved. Please try again later.";
    }
}

if ($topClass !== null || $diabetesTopClass !== null || $kidneyTopClass !== null) {
    $uploadedReportPath = $_SESSION["uploaded_report_path"] ?? null;
    $reportDirectory = realpath(__DIR__ . "/../../Backend/data");
    $resolvedReportPath = is_string($uploadedReportPath) ? realpath($uploadedReportPath) : false;

    if (
        $reportDirectory !== false &&
        $resolvedReportPath !== false &&
        dirname($resolvedReportPath) === $reportDirectory &&
        preg_match('/\Areport_[a-f0-9]+\.pdf\z/i', basename($resolvedReportPath))
    ) {
        if (unlink($resolvedReportPath)) {
            unset($_SESSION["uploaded_report_path"]);
        } else {
            error_log("Could not delete uploaded blood report: " . $resolvedReportPath);
        }
    } elseif ($uploadedReportPath !== null) {
        error_log("Refusing to delete an unexpected uploaded blood report path.");
    }
}

$markers = [
    "ALB" => ["label" => "Albumin", "field" => "alb"],
    "Alkphos" => ["label" => "Alkaline phosphatase", "field" => "alkphos"],
    "SGPT" => ["label" => "SGPT / ALT", "field" => "sgpt"],
    "SGOT" => ["label" => "SGOT / AST", "field" => "sgot"],
    "TB" => ["label" => "Total bilirubin", "field" => "tb"],
    "TP" => ["label" => "Total protein", "field" => "tp"],
];
$diabetesInputs = [
    "Gender" => $data["gender"] ?? null,
    "Age" => $data["age"] ?? null,
    "Smoking history" => $qa_data["smoking_status"] ?? null,
    "BMI" => $qa_data["bmi"] ?? null,
    "HbA1c" => $data["hba1c"] ?? null,
    "Blood glucose" => $data["glucose_level"] ?? null,
];
$diabetesProvidedCount = count(array_filter($diabetesInputs, function ($value) {
    return is_scalar($value) && trim((string) $value) !== "";
}));

function h($value) {
    return htmlspecialchars((string) $value, ENT_QUOTES, "UTF-8");
}

function render_explanation($explanation) {
    if (!is_array($explanation)) {
        return;
    }

    $factors = $explanation["possible_factors"] ?? [];
    $recommendations = $explanation["recommendations"] ?? [];
    ?>
    <section class="panel explainability-panel" aria-label="Prediction explanation">
        <div class="panel-heading">
            <div>
                <p class="eyebrow">POSSIBLE CONTRIBUTORS</p>
                <h2>Possible factors associated with <?= h($explanation["condition"] ?? "this result") ?></h2>
            </div>
        </div>
        <p class="explanation-summary"><?= h($explanation["summary"] ?? "") ?></p>
        <?php if ($factors): ?>
            <h3>Important findings and possible health links</h3>
            <ul class="explanation-list">
                <?php foreach ($factors as $factor): ?>
                    <li>
                        <div>
                            <strong><?= h($factor["label"] ?? "Input") ?>:</strong>
                            <span class="factor-value"><?= h($factor["value"] ?? "—") ?> <?= h($factor["unit"] ?? "") ?></span>
                            <?php if (!empty($factor["clinical_association"])): ?>
                                <span class="factor-context"><?= h($factor["clinical_association"]) ?></span>
                            <?php endif; ?>
                        </div>
                    </li>
                <?php endforeach; ?>
            </ul>
        <?php else: ?>
            <p class="explanation-empty">
                No available result provides a clear clinical explanation for this risk pattern. Review your report with a healthcare professional.
            </p>
        <?php endif; ?>

        <?php if ($recommendations): ?>
            <h3>Further recommendations</h3>
            <ul class="recommendation-list">
                <?php foreach ($recommendations as $recommendation): ?>
                    <li>
                        <strong><?= h($recommendation["factor"] ?? "Finding") ?>:</strong>
                        <?= h($recommendation["text"] ?? "") ?>
                    </li>
                <?php endforeach; ?>
            </ul>
        <?php endif; ?>
        <p class="explanation-limitation"><?= h($explanation["limitation"] ?? "") ?></p>
    </section>
    <?php
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Review your structured health overview and lab values.">
    <title>Your Results | MedPredict</title>
    <link rel="stylesheet" href="../CSS/res.css">
</head>
<body>
    <nav class="topbar">
        <a class="brand" href="home.php"><span class="brand-mark">M</span> MedPredict</a>
        <div class="nav-links">
            <a href="home.php">Home</a>
            <a href="qa.php">Health questionnaire</a>
            <a class="nav-logout" href="logout.php">Log out</a>
        </div>
    </nav>

    <main class="page-shell">
        <header class="page-heading">
            <div>
                <p class="eyebrow">YOUR HEALTH OVERVIEW</p>
                <h1>Prediction results</h1>
                <p class="subtitle">A clear summary of the model output and the lab values used.</p>
            </div>
            <a class="back-link" href="home.php"><span aria-hidden="true">&larr;</span> Back to dashboard</a>
        </header>

        <?php if ($predictionStorageError): ?>
            <section class="notice" role="alert">
                <span class="notice-icon" aria-hidden="true">i</span>
                <div><p><?= h($predictionStorageError) ?></p></div>
            </section>
        <?php endif; ?>

        <nav class="model-selector" aria-label="Choose prediction model">
            <button class="model-selector-button is-active" type="button" data-model-target="liver"
                    aria-controls="liver-panel" aria-pressed="true">Liver prediction</button>
            <button class="model-selector-button" type="button" data-model-target="diabetes"
                    aria-controls="diabetes-panel" aria-pressed="false">Diabetes prediction</button>
            <button class="model-selector-button" type="button" data-model-target="kidney"
                    aria-controls="kidney-panel" aria-pressed="false">Kidney prediction</button>
        </nav>

        <div class="model-panel" id="liver-panel" data-model-panel="liver">
        <?php if ($error): ?>
            <section class="notice" role="status">
                <span class="notice-icon" aria-hidden="true">i</span>
                <div>
                    <h2>Results aren't ready</h2>
                    <p><?= h($error) ?></p>
                    <?php if (!$data): ?><a href="home.php">Return to your dashboard</a><?php endif; ?>
                </div>
            </section>
        <?php endif; ?>

        <?php if ($prediction !== null && $topClass !== null): ?>
            <header class="model-section-heading">
                    <p class="eyebrow">LIVER MODEL</p>
                    <h2 id="liver-heading">Liver prediction</h2>
                    <p class="subtitle">Prediction based on your report and saved health questionnaire.</p>
                </header>
            <section class="summary-grid" aria-label="Prediction summary">
                
                <article class="summary-card featured-card">
                    <div class="summary-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.2c0 4.4 3.2 8.4 7.5 9.8 4.3-1.4 7.5-5.4 7.5-9.8V6L12 3Zm-1.1 12.8-3-3 1.4-1.4 1.6 1.6 4-4 1.4 1.4-5.4 5.4Z"/></svg>
                    </div>
                    <p class="card-label">Prediction</p>
                    <p class="summary-value"><?= $topClass === "1" ? "Higher risk pattern" : "Lower risk pattern" ?></p>
                    <p class="summary-caption">Risk screening result, not a diagnosis</p>
                </article>
                <article class="summary-card disease-chance-card <?= $topClass === "1" ? "risk-positive" : "risk-negative" ?>">
                    <div class="summary-icon confidence-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2Zm1 0v10h9A9 9 0 0 0 13 2Zm2.1 2.2A7 7 0 0 1 19.8 9h-4.7V4.2Z"/></svg>
                    </div>
                    <p class="card-label">Estimated disease probability</p>
                    <p class="summary-value"><?= h(number_format($probabilities["1"] * 100, 1)) ?><span class="value-unit">%</span></p>
                    <p class="summary-caption">Screening estimate, not clinical risk</p>
                </article>
                <article class="summary-card">
                    <div class="summary-icon values-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M4 5h16v2H4zm0 6h16v2H4zm0 6h10v2H4z"/></svg>
                    </div>
                    <p class="card-label">Lab markers analyzed</p>
                    <p class="summary-value"><?= h($availableLiverLabCount) ?></p>
                    <p class="summary-caption">Liver lab values provided by your report</p>
                </article>
            </section>

            <section class="content-grid">
                <article class="panel chart-panel">
                    <div class="panel-heading">
                        <div>
                            <p class="eyebrow">MODEL BREAKDOWN</p>
                            <h2>Class probabilities</h2>
                        </div>
                        <span class="chart-tag">Prediction distribution</span>
                    </div>
                    <p class="panel-description">How the model distributed its prediction across the available classes.</p>
                    <div class="probability-chart" role="img" aria-label="Class probability bar chart">
                        <?php foreach ($probabilities as $class => $probability): ?>
                            <?php $percentage = $probability * 100; ?>
                            <div class="bar-row">
                                <div class="bar-label">
                                    <span><?= (string) $class === "1" ? "Disease" : "No disease" ?></span>
                                    <strong><?= h(number_format($percentage, 1)) ?>%</strong>
                                </div>
                                <div class="bar-track" aria-hidden="true">
                                    <span class="bar-fill class-<?= h($class) ?><?= (string) $class === $topClass ? " is-top" : "" ?>"
                                          style="width: <?= h(number_format($percentage, 2, ".", "")) ?>%"></span>
                                </div>
                            </div>
                        <?php endforeach; ?>
                        <div class="axis-labels" aria-hidden="true"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
                    </div>
                    <p class="chart-footnote">Probabilities are model estimates, not a measure of overall health.</p>
                </article>

                <article class="panel markers-panel">
                    <div class="panel-heading">
                        <div>
                            <p class="eyebrow">FROM YOUR REPORT</p>
                            <h2>Lab values used</h2>
                        </div>
                        <span class="marker-count"><?= h($availableLiverLabCount) ?> markers provided</span>
                    </div>
                    <div class="marker-list">
                        <?php foreach ($markers as $key => $marker): ?>
                            <?php
                                $field = $marker["field"];
                                $value = $data[$field] ?? null;
                            ?>
                            <div class="marker-row">
                                <span class="marker-dot" aria-hidden="true"></span>
                                <span class="marker-name">
                                    <?= h($marker["label"]) ?>
                                </span>
                                <strong class="marker-value">
                                    <?= is_numeric($value) ? h($value) : "—" ?>
                                </strong>
                            </div>
                        <?php endforeach; ?>
                    </div>
                </article>
            </section>
            <?php render_explanation($prediction["explanation"] ?? null); ?>
        <?php endif; ?>

        <!-- <?php if ($prediction !== null && isset($prediction["note"])): ?>
            <p class="model-note"><?= h($prediction["note"]) ?></p>
        <?php endif; ?> -->
        </div>

        <div class="model-panel" id="diabetes-panel" data-model-panel="diabetes" hidden>
        <?php if ($diabetesError): ?>
            <section class="notice diabetes-notice" role="status">
                <span class="notice-icon" aria-hidden="true">i</span>
                <div>
                    <h2>Diabetes prediction isn't ready</h2>
                    <p><?= h($diabetesError) ?></p>
                    <?php if (!$data): ?><a href="home.php">Return to your dashboard</a><?php endif; ?>
                </div>
            </section>
        <?php endif; ?>

        <?php if ($diabetesPrediction !== null && $diabetesTopClass !== null): ?>
            <section class="diabetes-results" aria-labelledby="diabetes-heading">
                <header class="model-section-heading">
                    <p class="eyebrow">DIABETES MODEL</p>
                    <h2 id="diabetes-heading">Diabetes prediction</h2>
                    <p class="subtitle">Prediction based on your report and saved health questionnaire.</p>
                </header>

                <section class="summary-grid" aria-label="Diabetes prediction summary">
                    <article class="summary-card featured-card">
                        <div class="summary-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.2c0 4.4 3.2 8.4 7.5 9.8 4.3-1.4 7.5-5.4 7.5-9.8V6L12 3Zm-1.1 12.8-3-3 1.4-1.4 1.6 1.6 4-4 1.4 1.4-5.4 5.4Z"/></svg>
                        </div>
                        <p class="card-label">Prediction</p>
                        <p class="summary-value"><?= $diabetesTopClass === "1" ? "Higher risk pattern" : "Lower risk pattern" ?></p>
                        <p class="summary-caption">Risk screening result, not a diagnosis</p>
                    </article>
                    <article class="summary-card disease-chance-card <?= $diabetesTopClass === "1" ? "risk-positive" : "risk-negative" ?>">
                        <div class="summary-icon confidence-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2Zm1 0v10h9A9 9 0 0 0 13 2Zm2.1 2.2A7 7 0 0 1 19.8 9h-4.7V4.2Z"/></svg>
                        </div>
                        <p class="card-label">Estimated disease probability</p>
                        <p class="summary-value"><?= h(number_format($diabetesProbabilities["1"] * 100, 1)) ?><span class="value-unit">%</span></p>
                        <p class="summary-caption">Screening estimate, not clinical risk</p>
                    </article>
                    <article class="summary-card">
                        <div class="summary-icon values-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M4 5h16v2H4zm0 6h16v2H4zm0 6h10v2H4z"/></svg>
                        </div>
                        <p class="card-label">Features analyzed</p>
                        <p class="summary-value"><?= h($diabetesProvidedCount) ?></p>
                        <p class="summary-caption">Report and questionnaire values provided</p>
                    </article>
                </section>

                <section class="content-grid">
                    <article class="panel chart-panel">
                        <div class="panel-heading">
                            <div>
                                <p class="eyebrow">MODEL BREAKDOWN</p>
                                <h2>Class probabilities</h2>
                            </div>
                            <span class="chart-tag">Prediction distribution</span>
                        </div>
                        <p class="panel-description">How the model distributed its prediction across the available classes.</p>
                        <div class="probability-chart" role="img" aria-label="Diabetes class probability bar chart">
                            <?php foreach ($diabetesProbabilities as $class => $probability): ?>
                                <?php $percentage = $probability * 100; ?>
                                <div class="bar-row">
                                    <div class="bar-label">
                                        <span><?= (string) $class === "1" ? "Disease" : "No disease" ?></span>
                                        <strong><?= h(number_format($percentage, 1)) ?>%</strong>
                                    </div>
                                    <div class="bar-track" aria-hidden="true">
                                        <span class="bar-fill class-<?= h($class) ?><?= (string) $class === $diabetesTopClass ? " is-top" : "" ?>"
                                              style="width: <?= h(number_format($percentage, 2, ".", "")) ?>%"></span>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                            <div class="axis-labels" aria-hidden="true"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
                        </div>
                        <p class="chart-footnote">Probabilities are model estimates, not a measure of overall health.</p>
                    </article>

                    <article class="panel markers-panel">
                        <div class="panel-heading">
                            <div>
                                <p class="eyebrow">INPUT VALUES</p>
                                <h2>Values analyzed</h2>
                            </div>
                            <span class="marker-count"><?= h($diabetesProvidedCount) ?> provided</span>
                        </div>
                        <div class="marker-list">
                            <?php foreach ($diabetesInputs as $label => $value): ?>
                                <div class="marker-row">
                                    <span class="marker-dot" aria-hidden="true"></span>
                                    <span class="marker-name">
                                        <?= h($label) ?>
                                    </span>
                                    <strong class="marker-value"><?= is_numeric($value) ? h($value) : h($value ?? "—") ?></strong>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </article>
                </section>
                <?php render_explanation($diabetesPrediction["explanation"] ?? null); ?>
                <!-- <?php if (isset($diabetesPrediction["note"])): ?>
                    <p class="model-note"><?= h($diabetesPrediction["note"]) ?></p>
                <?php endif; ?> -->
            </section>
        <?php endif; ?>
        </div>

        <div class="model-panel" id="kidney-panel" data-model-panel="kidney" hidden>
        <?php if ($kidneyError): ?>
            <section class="notice diabetes-notice" role="status">
                <span class="notice-icon" aria-hidden="true">i</span>
                <div>
                    <h2>Kidney prediction isn't ready</h2>
                    <p><?= h($kidneyError) ?></p>
                    <?php if (!$data): ?><a href="home.php">Return to your dashboard</a><?php endif; ?>
                </div>
            </section>
        <?php endif; ?>

        <?php if ($kidneyPrediction !== null && $kidneyTopClass !== null): ?>
            <section class="diabetes-results" aria-labelledby="kidney-heading">
                <header class="model-section-heading">
                    <p class="eyebrow">KIDNEY MODEL</p>
                    <h2 id="kidney-heading">Kidney prediction</h2>
                    <p class="subtitle">Prediction based on your report and the kidney model's required inputs.</p>
                </header>

                <section class="summary-grid" aria-label="Kidney prediction summary">
                    <article class="summary-card featured-card">
                        <div class="summary-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.2c0 4.4 3.2 8.4 7.5 9.8 4.3-1.4 7.5-5.4 7.5-9.8V6L12 3Zm-1.1 12.8-3-3 1.4-1.4 1.6 1.6 4-4 1.4 1.4-5.4 5.4Z"/></svg>
                        </div>
                        <p class="card-label">Prediction</p>
                        <p class="summary-value"><?= $kidneyTopClass === "1" ? "Higher risk pattern" : "Lower risk pattern" ?></p>
                        <p class="summary-caption">Risk screening result, not a diagnosis</p>
                    </article>
                    <article class="summary-card disease-chance-card <?= $kidneyTopClass === "1" ? "risk-positive" : "risk-negative" ?>">
                        <div class="summary-icon confidence-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2Zm1 0v10h9A9 9 0 0 0 13 2Zm2.1 2.2A7 7 0 0 1 19.8 9h-4.7V4.2Z"/></svg>
                        </div>
                        <p class="card-label">Estimated disease probability</p>
                        <p class="summary-value"><?= h(number_format($kidneyProbabilities["1"] * 100, 1)) ?><span class="value-unit">%</span></p>
                        <p class="summary-caption">Screening estimate, not clinical risk</p>
                    </article>
                    <article class="summary-card">
                        <div class="summary-icon values-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M4 5h16v2H4zm0 6h16v2H4zm0 6h10v2H4z"/></svg>
                        </div>
                        <p class="card-label">Features analyzed</p>
                        <p class="summary-value"><?= h(count($kidneyFeatures)) ?></p>
                        <p class="summary-caption">Report and questionnaire values provided</p>
                    </article>
                </section>

                <section class="content-grid">
                    <article class="panel chart-panel">
                        <div class="panel-heading">
                            <div>
                                <p class="eyebrow">MODEL BREAKDOWN</p>
                                <h2>Class probabilities</h2>
                            </div>
                            <span class="chart-tag">Prediction distribution</span>
                        </div>
                        <p class="panel-description">How the model distributed its prediction across the available classes.</p>
                        <div class="probability-chart" role="img" aria-label="Kidney class probability bar chart">
                            <?php foreach ($kidneyProbabilities as $class => $probability): ?>
                                <?php $percentage = $probability * 100; ?>
                                <div class="bar-row">
                                    <div class="bar-label">
                                        <span><?= (string) $class === "1" ? "Disease" : "No disease" ?></span>
                                        <strong><?= h(number_format($percentage, 1)) ?>%</strong>
                                    </div>
                                    <div class="bar-track" aria-hidden="true">
                                        <span class="bar-fill class-<?= h($class) ?><?= (string) $class === $kidneyTopClass ? " is-top" : "" ?>"
                                              style="width: <?= h(number_format($percentage, 2, ".", "")) ?>%"></span>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                            <div class="axis-labels" aria-hidden="true"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
                        </div>
                        <p class="chart-footnote">Probabilities are model estimates, not a measure of overall health.</p>
                    </article>

                    <article class="panel markers-panel">
                        <div class="panel-heading">
                            <div>
                                <p class="eyebrow">INPUT VALUES</p>
                                <h2>Values analyzed</h2>
                            </div>
                            <span class="marker-count"><?= h(count($kidneyFeatures)) ?> provided</span>
                        </div>
                        <div class="marker-list">
                            <?php foreach ($kidneyInputs as $label => $input): ?>
                                <div class="marker-row">
                                    <span class="marker-dot" aria-hidden="true"></span>
                                    <span class="marker-name">
                                        <?= h($label) ?>
                                    </span>
                                    <strong class="marker-value"><?= is_numeric($input["value"]) ? h($input["value"]) : "—" ?></strong>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </article>
                </section>
                <?php render_explanation($kidneyPrediction["explanation"] ?? null); ?>
                <!-- <?php if (isset($kidneyPrediction["note"])): ?>
                    <p class="model-note"><?= h($kidneyPrediction["note"]) ?></p>
                <?php endif; ?> -->
            </section>
        <?php endif; ?>
        </div>

    

    </main>

    <script src="../script/model-selector.js"></script> 
</body>
</html>
