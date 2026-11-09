<?php
require_once __DIR__ . "/../api_config.php";
require_once __DIR__ . "/../api_config.php";
$diabetesError = "";
$diabetesPrediction = null;

$diabetesRequiredFields = [
    "gender" => ["source" => $data, "key" => "gender", "label" => "gender"],
    "age" => ["source" => $data, "key" => "age", "label" => "age"],
    "smoking_history" => ["source" => $qa_data, "key" => "smoking_status", "label" => "smoking status"],
    "bmi" => ["source" => $qa_data, "key" => "bmi", "label" => "BMI"],
    "HbA1c_level" => ["source" => $data, "key" => "hba1c", "label" => "HbA1c"],
];
$missingDiabetesFields = [];

foreach ($diabetesRequiredFields as $field => $required) {
    $source = $required["source"];
    $value = is_array($source) ? ($source[$required["key"]] ?? null) : null;
    if (!is_scalar($value) || trim((string) $value) === "" ||
        ($field !== "smoking_history" && !is_numeric($value))) {
        $missingDiabetesFields[] = $required["label"];
    }
}

if ($data && !$missingDiabetesFields) {
    $diabetesFeatures = [
        "gender" => (int) $data["gender"],
        "age" => (int) $data["age"],
        "smoking_history" => trim((string) $qa_data["smoking_status"]),
        "bmi" => (float) $qa_data["bmi"],
        "HbA1c_level" => (float) $data["hba1c"],
    ];
    if (isset($data["glucose_level"]) && is_numeric($data["glucose_level"])) {
        $diabetesFeatures["blood_glucose_level"] = (float) $data["glucose_level"];
    }
    $diabetesCurl = curl_init(medpredict_api_url("predict/diabetes"));
    curl_setopt_array($diabetesCurl, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($diabetesFeatures),
        CURLOPT_HTTPHEADER => medpredict_api_headers(["Content-Type: application/json", "Accept: application/json"]),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => 15,
    ]);

    $diabetesApiResponse = curl_exec($diabetesCurl);
    $diabetesCurlError = curl_error($diabetesCurl);
    $diabetesStatusCode = curl_getinfo($diabetesCurl, CURLINFO_HTTP_CODE);
    curl_close($diabetesCurl);

    if ($diabetesApiResponse === false) {
        $diabetesError = "The diabetes prediction service is unavailable right now. Please try again later.";
        error_log("Diabetes prediction request failed: " . $diabetesCurlError);
    } elseif ($diabetesStatusCode < 200 || $diabetesStatusCode >= 300) {
        $diabetesError = "The diabetes prediction service couldn't process this report. Please try again later.";
        error_log("Diabetes prediction returned HTTP " . $diabetesStatusCode . ": " . $diabetesApiResponse);
    } else {
        $diabetesPrediction = json_decode($diabetesApiResponse, true);
        if (!is_array($diabetesPrediction) || !isset($diabetesPrediction["class_probabilities"]) ||
            !is_array($diabetesPrediction["class_probabilities"])) {
            $diabetesPrediction = null;
            $diabetesError = "The diabetes prediction service returned an unexpected response.";
            error_log("Diabetes prediction response had an unexpected format.");
        }
    }
} elseif ($data) {
    $diabetesError = "Diabetes prediction needs " . implode(", ", $missingDiabetesFields) .
        " in the report or saved health questionnaire.";
}
?>
