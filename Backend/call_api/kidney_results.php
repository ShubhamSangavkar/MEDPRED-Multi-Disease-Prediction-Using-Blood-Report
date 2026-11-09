<?php
require_once __DIR__ . "/../api_config.php";
require_once __DIR__ . "/../api_config.php";
$kidneyError = "";
$kidneyPrediction = null;
$kidneyFeatures = [];
$kidneyInputs = [];
$kidneyLabels = [
    "sg" => "Specific gravity",
    "al" => "Urine albumin",
    "bgr" => "Blood glucose",
    "bu" => "Blood urea",
    "sc" => "Serum creatinine",
    "sod" => "Sodium",
    "pot" => "Potassium",
    "hemo" => "Hemoglobin",
    "htn" => "Hypertension",
    "dm" => "Heart Disease",
];
$kidneyRequiredFields = ["age" => "age", "hemo" => "hemoglobin"];
$missingKidneyFields = [];

foreach ($kidneyRequiredFields as $field => $label) {
    $value = $data[$field] ?? null;
    $invalid = !is_numeric($value);
    if (in_array($field, ["age", "hemo"], true) &&
        (!$invalid && (float) $value <= 0)) {
        $invalid = true;
    }
    if ($invalid) {
        $missingKidneyFields[] = $label;
    }
}

if ($data && !$missingKidneyFields) {
    $kidneyFeatures = [
        "age" => (int) $data["age"],
        "hemo" => (float) $data["hemo"],
        "gender" => isset($data["gender"]) && is_numeric($data["gender"])
            ? (int) $data["gender"]
            : null,
    ];
    foreach (["sg", "al", "bu", "sc", "sod", "pot"] as $field) {
        if (isset($data[$field]) && is_numeric($data[$field])) {
            $kidneyFeatures[$field] = (float) $data[$field];
        }
    }
    if (isset($data["glucose_level"]) && is_numeric($data["glucose_level"])) {
        $kidneyFeatures["bgr"] = (float) $data["glucose_level"];
    }
    foreach (["htn", "dm"] as $field) {
        if (isset($qa_data[$field]) && is_numeric($qa_data[$field])) {
            $kidneyFeatures[$field] = (int) $qa_data[$field];
        }
    }
    $kidneyCurl = curl_init(medpredict_api_url("predict/kidney"));
    curl_setopt_array($kidneyCurl, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($kidneyFeatures),
        CURLOPT_HTTPHEADER => medpredict_api_headers(["Content-Type: application/json", "Accept: application/json"]),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => 15,
    ]);

    $kidneyApiResponse = curl_exec($kidneyCurl);
    $kidneyCurlError = curl_error($kidneyCurl);
    $kidneyStatusCode = curl_getinfo($kidneyCurl, CURLINFO_HTTP_CODE);
    curl_close($kidneyCurl);

    if ($kidneyApiResponse === false) {
        $kidneyError = "The kidney prediction service is unavailable right now. Please try again later.";
        error_log("Kidney prediction request failed: " . $kidneyCurlError);
    } elseif ($kidneyStatusCode < 200 || $kidneyStatusCode >= 300) {
        $kidneyError = "The kidney prediction service couldn't process this report. Please try again later.";
        error_log("Kidney prediction returned HTTP " . $kidneyStatusCode . ": " . $kidneyApiResponse);
    } else {
        $kidneyPrediction = json_decode($kidneyApiResponse, true);
        if (!is_array($kidneyPrediction) || !isset($kidneyPrediction["class_probabilities"]) ||
            !is_array($kidneyPrediction["class_probabilities"])) {
            $kidneyPrediction = null;
            $kidneyError = "The kidney prediction service returned an unexpected response.";
            error_log("Kidney prediction response had an unexpected format.");
        } else {
            $kidneyInputs["Age"] = ["value" => $kidneyFeatures["age"]];
            foreach ($kidneyLabels as $field => $label) {
                $kidneyInputs[$label] = [
                    "value" => $kidneyFeatures[$field] ?? null,
                ];
            }
        }
    }
} elseif ($data) {
    $kidneyError = "Kidney prediction needs " . implode(", ", $missingKidneyFields) .
        " in the blood report.";
}
?>
