# Lab Report Extractor API

A FastAPI service that wraps `lab_report_extractor.py`: upload a medical lab
report PDF (any lab / any template — text-based or scanned) and get back
structured `test_name / result / unit / ref_range` rows as JSON.

## 1. Install

```bash
# system packages needed for OCR fallback on scanned PDFs
sudo apt-get install -y poppler-utils tesseract-ocr     # Debian/Ubuntu
# brew install poppler tesseract                        # macOS

pip install -r requirements.txt
```

## 2. Run

```bash
uvicorn app:app --reload --port 8000
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI, or use curl:

```bash
curl -X POST "http://127.0.0.1:8000/extract" \
     -F "file=@/path/to/report.pdf"
```

## 3. Endpoints

| Method | Path             | Description                                   |
|--------|------------------|------------------------------------------------|
| GET    | `/health`        | Liveness check                                 |
| POST   | `/extract`       | Upload **one** PDF, get structured JSON back   |
| POST   | `/standardize`   | Map extracted test names to canonical feature names |
| POST   | `/predict/liver` | Predict using age, gender, and six liver markers |
| POST   | `/predict/diabetes` | Predict using gender, age, smoking history, BMI, HbA1c, and blood glucose |
| POST   | `/predict/kidney` | Predict using age, kidney markers, hemoglobin, hypertension, and diabetes status |

All routes are served by the FastAPI application on port `8000` by default.
Interactive API documentation is available at `/docs`; the generated OpenAPI
document is at `/openapi.json`. The API does not define authentication.

### `/health`

`GET /health` takes no input and returns HTTP 200:

```json
{ "status": "ok" }
```

### `/extract`

Send one PDF as `multipart/form-data` in the required `file` field. Files must
be PDFs and no larger than 25 MB. A successful response is HTTP 200 with
`filename`, `row_count`, and `rows`; each row contains `test_name`, `result`,
`unit`, `ref_range`, `flag`, `section`, `source_page`, and `source_file`.

Errors: HTTP 400 for a non-PDF upload, HTTP 413 when the size limit is exceeded,
HTTP 422 when extraction fails, and HTTP 422 when the required file is absent.
The response schema is shown below.

### `/standardize`

Send JSON containing a `tests` array. Each item should contain a `test_name`;
other item properties are retained in the output.

```json
{
  "tests": [
    { "test_name": "Serum Creatinine", "result": "1.1", "unit": "mg/dL" },
    { "test_name": "Unrecognized panel", "result": "7" }
  ]
}
```

The response separates recognized rows from names that could not be matched.
Recognized rows retain their input properties, add `original_test_name`, and
replace `test_name` with its canonical name.

```json
{
  "features": [
    {
      "test_name": "sc",
      "result": "1.1",
      "unit": "mg/dL",
      "original_test_name": "Serum Creatinine"
    }
  ],
  "unmatched_tests": ["Unrecognized panel"]
}
```

Canonical names currently include `alb`, `alkphos`, `sgpt`, `sgot`, `tb`,
`tp`, `hba1c`, `glucose_level`, `sg`, `al`, `bu`, `sc`, `sod`, `pot`, and
`hemo`. This endpoint matches names; it does not convert units or validate
clinical ranges. An invalid request body returns HTTP 422.

### `/predict/liver` inputs

Send JSON with required `Age` (integer, 1–120) and `Gender` (integer), plus
optional numeric `ALB`, `Alkphos`, `Sgpt`, `Sgot`, `TB`, and `TP`. The six lab
markers may be omitted. Omitted markers are passed to XGBoost as missing
values; no defaults or substitute values are used. The response lists omitted
markers in `missing_features`.
Each prediction response includes a condition-specific summary, up to three
clinically interpretable factors selected from disease-increasing TreeSHAP
contributions, and recommendations relevant to those factors. These are
possible associations, not confirmed causes or a diagnosis; clinical review
and the laboratory's own reference intervals take precedence.

### `/predict/diabetes` inputs

Send JSON with required integer `gender`, integer `age` (1–120),
`smoking_history`, numeric `bmi` (>0 and ≤100), and numeric `HbA1c_level`
(>0 and ≤20). `smoking_history` accepts `Never`, `No Info`, `Current`,
`Former`, `Ever`, or `Not current` (case-insensitive, encoded as 0–5 in that
order). Optional numeric `blood_glucose_level` must be greater than zero when
provided. The model feature order is `gender`, `age`, `smoking_history`,
`bmi`, `HbA1c_level`, `blood_glucose_level`. When blood glucose is omitted,
it is passed to XGBoost as missing; no default or substitute value is used.

### `/predict/kidney` inputs

Send JSON with required integer `age` (1–120) and numeric `hemo` (>0).
Optional numeric `sg`, `al`, `bgr`, `bu`, `sc`, `sod`, and `pot` must be
non-negative when supplied; optional integer `htn` and `dm` are 0/1 indicators
for hypertension and diabetes. Optional integer `gender` is 0 or 1 and is used
only for hemoglobin explanation context, not as a model feature. The model
feature order is `age`, `sg`, `al`, `bgr`, `bu`, `sc`, `sod`, `pot`, `hemo`,
`htn`, `dm`. All omitted optional model features are passed to XGBoost as
missing values; no defaults or substitute values are used. The response lists
omitted model features in `missing_features`.

### Prediction request and response contracts

All three prediction endpoints accept a JSON object and return HTTP 200 with
the same response structure. `predicted_class` is `0` or `1`; the matching
`class_probabilities` values are probabilities rounded to six decimal places.
Class `1` means the model predicts the disease class, and class `0` means the
model predicts the non-disease class.

```json
{
  "model": "diabetes_xgboost",
  "predicted_class": 1,
  "class_probabilities": { "0": 0.12, "1": 0.88 },
  "missing_features": ["blood_glucose_level"],
  "explanation": {
    "condition": "diabetes",
    "summary": "Condition-specific risk summary and estimated probability.",
    "possible_factors": [
      {
        "feature": "HbA1c_level",
        "label": "HbA1c",
        "value": 6.8,
        "unit": "%",
        "clinical_association": "Clinical context for this model factor."
      }
    ],
    "recommendations": [
      { "factor": "HbA1c", "text": "Discuss the result with a clinician." }
    ],
    "limitation": "Factors are possible associations, not confirmed causes."
  },
  "note": "This machine-learning prediction is not a medical diagnosis."
}
```

`explanation.possible_factors` contains up to three positive TreeSHAP factors
for which the API has clinical context; it can be empty. Recommendations are
associated with those factors and can also be empty. `missing_features` lists
model inputs supplied as missing. Diabetes reports the missing input as
`blood_glucose_level`; liver and kidney use their model feature names. A
request failing input validation returns HTTP 422; a model or explanation
failure returns HTTP 500 with a `detail` message.

### `/extract` response shape

```json
{
  "filename": "report.pdf",
  "row_count": 42,
  "rows": [
    {
      "test_name": "Haemoglobin",
      "result": "13.6",
      "unit": "gm/dL",
      "ref_range": "13.0 - 17.0",
      "flag": "",
      "section": "CBC",
      "source_page": 6,
      "source_file": "report.pdf"
    }
  ]
}
```

## 4. Quick test

```bash
python test_client.py sample1.pdf sample2.pdf
```

## 5. How extraction works (`lab_report_extractor.py`)

1. **Text extraction** via `pdfplumber`. If a page has (almost) no text layer
   (scanned/photographed reports), it automatically falls back to OCR
   (`pdf2image` + `pytesseract`).
2. **Glyph-dedup repair** — some PDF generators render bold text by
   duplicating every character N times in the text layer
   (`"HHHHaaaaeeee..."` for `"Haemo..."`). This is detected and fixed per
   line automatically.
3. **Row parsing** — a cascade of regex strategies per line handles the most
   common report layouts:
   - `Name  Result  Unit  RefRange` on one line (e.g. HOD/Pathkind style)
   - `Name - Result Unit RefRange` dash/colon style (e.g. local lab style)
   - `Name` on its own line, with `Result Unit RefRange` on the line that
     follows (e.g. Max Lab style, where a Method/technique line sits between)
   - Section/panel headings (e.g. "CBC", "Lipid Profile") are tracked and
     attached to each row that follows them.

## 6. Limitations

Lab report layouts are **not standardized**, so this is a best-effort
heuristic extractor, not a guaranteed-perfect parser:

- Free-text remarks/notes paragraphs occasionally get mis-parsed as rows if
  they contain a bare number (false positives). Filter by `section` or
  sanity-check `result` as numeric where you need precision.
- Multi-column "unit + range" cells that omit whitespace between the unit
  and first range bound can sometimes be split incorrectly.
- Always spot check output before using it for anything clinical — this
  tool is for structuring/triage, not diagnosis.

## 7. Files

- `lab_report_extractor.py` — the extraction engine (usable standalone / CLI)
- `app.py` — FastAPI wrapper
- `requirements.txt` — Python deps (+ system deps noted in comments)
- `test_client.py` — simple script to hit a running server
