<?php
require_once __DIR__ . "/../api_config.php";
require_once __DIR__ . "/../api_config.php";

// Your existing PHP array
// $data = ...;

// Select the 8 features required by the liver model
$features = [
    "Age"     => (float) $data["age"],
    "Gender"  => (int) $data["gender"],
    "ALB"     => (float) $data["alb"],
    "Alkphos" => (float) $data["alkphos"],
    "Sgpt"    => (float) $data["sgpt"],
    "Sgot"    => (float) $data["sgot"],
    "TB"      => (float) $data["tb"],
    "TP"      => (float) $data["tp"]
];

// Encode features as JSON
$jsonData = json_encode($features);

// Call FastAPI
$ch = curl_init(medpredict_api_url("predict/liver"));

curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonData);
curl_setopt($ch, CURLOPT_HTTPHEADER, medpredict_api_headers([
    "Content-Type: application/json",
    "Accept: application/json"
]));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);

if ($response === false) {
    die("API connection error: " . curl_error($ch));
}

$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

// Get API result
$result = json_decode($response, true);

if ($httpCode === 200 && is_array($result)) {
    echo "<h3>Liver Model API Result</h3>";
    echo "<pre>";
    print_r($result);
    echo "</pre>";
} else {
    echo "API request failed: " . htmlspecialchars($response);
}
?>