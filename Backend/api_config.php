<?php
// Shared configuration for PHP-to-FastAPI requests.
$configPath = __DIR__ . '/config.local.php';
if (!is_file($configPath)) {
    throw new RuntimeException('Missing Backend/config.local.php.');
}
$medpredictConfig = require $configPath;
$medpredictApiBase = rtrim((string)($medpredictConfig['api_base_url'] ?? ''), '/');
$medpredictApiKey = (string)($medpredictConfig['api_key'] ?? '');

if ($medpredictApiBase === '' || !filter_var($medpredictApiBase, FILTER_VALIDATE_URL)) {
    throw new RuntimeException('Set a valid HTTPS api_base_url in Backend/config.local.php.');
}
if (stripos($medpredictApiBase, 'https://') !== 0) {
    throw new RuntimeException('The deployed API URL must use HTTPS.');
}
if ($medpredictApiKey === '') {
    throw new RuntimeException('Set api_key in Backend/config.local.php.');
}

function medpredict_api_url(string $path): string
{
    global $medpredictApiBase;
    return $medpredictApiBase . '/' . ltrim($path, '/');
}

function medpredict_api_headers(array $extra = []): array
{
    global $medpredictApiKey;
    return array_merge(['X-MedPredict-Key: ' . $medpredictApiKey], $extra);
}
