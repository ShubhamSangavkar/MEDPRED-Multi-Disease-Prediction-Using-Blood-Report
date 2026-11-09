# MedPredict: free deployment notes

This project uses PHP + MySQL for the website and a separate FastAPI service for OCR and XGBoost predictions.

## Hosting layout

- PHP + MySQL: InfinityFree (free PHP/MySQL hosting)
- FastAPI: Render Free Web Service using the Dockerfile at repository root
- Source: private GitHub repository

This is for a college demonstration only. Do not upload real patient reports or rely on model outputs for diagnosis. Free plans can sleep, restart, lose local files, and change their limits.

## 0. Before uploading

1. The uploaded project contained a database password in `Backend/db_config.php`. Treat it as exposed: change/rotate it anywhere it was used. The replacement source removes the hardcoded password.
2. Do not put `Backend/config.local.php`, real reports, or database exports with real records in GitHub.
3. Create a private GitHub repository. Upload the project with `.gitignore`, `Dockerfile`, and `database_schema.sql`.
4. You can omit `Model_training/` from the deployed repo if you only need inference; the trained model files are already in `Backend/Api/models/`.

## 1. Deploy FastAPI on Render

1. Push the repository to a **private** GitHub repository. The deployment ZIP includes a `.gitignore` that excludes `Backend/config.local.php` and uploaded PDF files.
2. In Render, create **New > Web Service**, connect the repository, and choose **Docker**.
3. Set Dockerfile path to `./Dockerfile` and select the Free instance if it is offered to your account.
4. Add environment variable `MEDPREDICT_API_KEY` with a long random value (at least 32 random characters). Save it privately; you will also put the same value in `Backend/config.local.php`.
5. Deploy. The service URL should be HTTPS, e.g. `https://your-service.onrender.com`.
6. Test `https://your-service.onrender.com/health`. It should return `{"status":"ok"}`. `/docs` is available for API reference.

If deployment fails from memory limits, inspect Render build/runtime logs. The free instance is not guaranteed to have enough memory for all Python/XGBoost dependencies; don't treat a successful build as proof that every model endpoint works.

## 2. Create the MySQL database

1. Create a free PHP hosting account and a website/subdomain.
2. In the hosting control panel, create a MySQL database and user. Copy the exact host, database name, username and password.
3. Open phpMyAdmin for that database and import `database_schema.sql`.
4. Check that the tables `users`, `health_questionnaires`, `blood_reports`, `blood_test_results`, `blood_test_observations`, `prediction_results`, and `admin_accounts` exist.

## 3. Configure local credentials on PHP hosting

1. Copy `Backend/config.local.example.php` to `Backend/config.local.php`.
2. Fill in the MySQL values from the hosting panel.
3. Set `api_base_url` to the HTTPS Render service URL (no trailing slash).
4. Set `api_key` to exactly the same value as Render's `MEDPREDICT_API_KEY`.
5. Upload `index.php`, the root `.htaccess`, `Backend/` (but skip `Backend/Api/`, because Python runs on Render), and `Frontend/` to the PHP host's `htdocs` directory. Upload the `Backend/.htaccess` file too.
6. Confirm PHP extensions `mysqli` and `curl` are enabled.

If your hosting provider does not let you create a private config file, keep `config.local.php` inside `Backend/` and ensure the included `Backend/.htaccess` denies direct web access to it. Do not share this file or paste its contents into chat.

## 4. Test in this order

1. Open the website homepage.
2. Register a test account using fictional data.
3. Log in.
4. Save the health questionnaire.
5. Upload a small sample PDF with fictional/demo values only.
6. Confirm extraction and standardization work.
7. Open the result page and test each prediction endpoint with synthetic inputs.
8. Check PHP and Render logs for errors.

The Render free service may sleep after inactivity and the first request can take around a minute to wake. Its filesystem is ephemeral; this app's extraction endpoint uses temporary files, while the PHP side deletes its uploaded report after predictions are produced.

## 5. Important known limitations / checks

- This archive did not include a `.sql` export. The included schema was reconstructed from the SQL statements and feature names used by the current PHP code. Test all workflows and adjust it if your local database had additional columns or constraints.
- Render Free Web Services use an ephemeral filesystem and have resource limits. They are for demos/testing, not production medical data.
- InfinityFree free hosting allows outbound HTTP(S) cURL requests, but its own browser security layer may challenge automated/inbound API clients. Use the PHP site in a normal browser. Do not expose PHP endpoints as public APIs.
- Some free PHP hosts impose upload size/time limits. Check their control panel and set the PHP upload limit high enough for your 25 MB API cap, or lower `MAX_FILE_SIZE_MB` in `Backend/Api/app.py`.
- Protect admin creation. `Backend/create_admin.php` is CLI-only and won't run from a browser; create an admin through a trusted local CLI workflow or temporarily create a properly hashed password using PHP CLI before deployment.
- Predictions are educational outputs only, not a diagnosis or substitute for a qualified clinician. Do not upload real personal medical data to this free demo.
