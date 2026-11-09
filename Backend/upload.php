<?php

session_start();
require_once __DIR__ . "/api_config.php";
require_once __DIR__ . "/api_config.php";

function redirectWithUploadError(string $message): void
{
    $_SESSION["upload_error"] = $message;
    header("Location: ../Frontend/Pages/home.php");
    exit;
}

if (!isset($_SESSION["user_id"])) {
    header("Location: login.php");
    exit;
}

$user_id = $_SESSION["user_id"];


if (isset($_FILES['pdf'])) {

    $file = $_FILES['pdf'];

    if ($file['error'] !== UPLOAD_ERR_OK) {
        die("Upload failed");
    }

    
    $extension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));

    if ($extension !== "pdf") {
        die("Only PDF files are allowed");
    }

    $uploadDir = __DIR__ . DIRECTORY_SEPARATOR . "data" . DIRECTORY_SEPARATOR;

    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0777, true);
    }

    $fileName = uniqid("report_") . ".pdf";
    $filePath = $uploadDir . $fileName;

    if (!move_uploaded_file($file['tmp_name'], $filePath)) {
        die("Could not save PDF");
    }

    $_SESSION["uploaded_report_path"] = realpath($filePath);

    $apiUrl = medpredict_api_url("extract");

    $curl = curl_init();

    $postData = [
        "file" => new CURLFile(
            realpath($filePath),
            "application/pdf",
            $file['name']
        )
    ];

    curl_setopt($curl, CURLOPT_URL, $apiUrl);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, $postData);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($curl, CURLOPT_CONNECTTIMEOUT, 10);
    curl_setopt($curl, CURLOPT_TIMEOUT, 120);
    curl_setopt($curl, CURLOPT_HTTPHEADER, medpredict_api_headers(["Accept: application/json"]));
    curl_setopt($curl, CURLOPT_CONNECTTIMEOUT, 10);
    curl_setopt($curl, CURLOPT_TIMEOUT, 120);
    curl_setopt($curl, CURLOPT_HTTPHEADER, medpredict_api_headers(["Accept: application/json"]));

    $response = curl_exec($curl);

    if ($response === false) {
        die("API Error: " . curl_error($curl));
    }

    $extractStatus = curl_getinfo($curl, CURLINFO_HTTP_CODE);
    curl_close($curl);

    $extracted = json_decode($response, true);
    if (
        $extractStatus < 200 ||
        $extractStatus >= 300 ||
        !is_array($extracted) ||
        !isset($extracted["rows"]) ||
        !is_array($extracted["rows"])
    ) {
        redirectWithUploadError(
            "We couldn't read this PDF. Please upload a clear, text-readable blood report and try again."
        );
    }

    if (count($extracted["rows"]) === 0) {
        redirectWithUploadError(
            "We couldn't find any lab results in this PDF. Please upload a blood report that clearly shows test names and result values. Scanned or password-protected PDFs may not be supported."
        );
    }

    $requestData = json_encode([
         "tests" => $extracted["rows"]
    ]);




    $ch = curl_init(medpredict_api_url("standardize"));



    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $requestData,
        CURLOPT_HTTPHEADER => medpredict_api_headers([
            "Content-Type: application/json",
            "Accept: application/json"
        ]),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT => 30
    ]);



    $response = curl_exec($ch);



    if ($response === false) {
        die("Error: " . curl_error($ch));
    }



    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);



    // Display standardized JSON
    if ($status >= 200 && $status < 300) {
        $result = json_decode($response, true);
        $features = is_array($result) ? ($result["features"] ?? null) : null;
        if (is_array($features) && count($features) > 0) {
            try {
                include "store_results.php";
            } catch (Throwable $exception) {
                error_log("Could not store extracted lab parameters: " . $exception->getMessage());
                redirectWithUploadError(
                    "We extracted the lab values but couldn't save them. Please try uploading the report again."
                );
            }

            $_SESSION["upload_success"] = "Lab parameters were extracted and saved successfully.";
            header("Location: ../Frontend/Pages/qa.php");
            exit;
        } elseif (is_array($features)) {
            redirectWithUploadError(
                "We couldn't identify any supported lab values in this PDF. Please try a blood report with clearly labeled test names and result values."
            );
        } else {
            redirectWithUploadError(
                "We couldn't process this PDF. Please check that it contains readable lab results, then try again."
            );
        }




        
    } else {
        echo "API Error: " . htmlspecialchars($response);
    }


} else {
    echo "No PDF selected";
}


?>