from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
import xgboost as xgb


# --------------------------------------------------------------------------- #
# Labels, units, priorities
# --------------------------------------------------------------------------- #

_LABELS = {
    "Age": "Age",
    "Gender": "Gender",
    "ALB": "Serum albumin",
    "Alkphos": "Alkaline phosphatase",
    "Sgpt": "ALT / SGPT",
    "Sgot": "AST / SGOT",
    "TB": "Total bilirubin",
    "TP": "Total protein",
    "gender": "Gender",
    "age": "Age",
    "smoking_history": "Smoking history",
    "bmi": "BMI",
    "HbA1c_level": "HbA1c",
    "blood_glucose_level": "Blood glucose",
    "hypertension": "Hypertension",
    "heart_disease": "Heart disease",
    "sg": "Urine specific gravity",
    "al": "Urine albumin",
    "bgr": "Blood glucose",
    "bu": "Blood urea",
    "sc": "Serum creatinine",
    "sod": "Sodium",
    "pot": "Potassium",
    "hemo": "Hemoglobin",
    "htn": "Hypertension",
    "dm": "Diabetes",
}

_UNITS = {
    "ALB": "g/dL",
    "Alkphos": "U/L",
    "Sgpt": "U/L",
    "Sgot": "U/L",
    "TB": "mg/dL",
    "TP": "g/dL",
    "bmi": "kg/m²",
    "HbA1c_level": "%",
    "blood_glucose_level": "mg/dL",
    "bgr": "mg/dL",
    "bu": "mg/dL",
    "sc": "mg/dL",
    "sod": "mmol/L",
    "pot": "mmol/L",
    "hemo": "g/dL",
}

URGENT, SOON, ROUTINE = "urgent", "soon", "routine"
_PRIORITY_RANK = {URGENT: 0, SOON: 1, ROUTINE: 2}
_PRIORITY_TEXT = {
    URGENT: "Seek medical care today",
    SOON: "See a doctor within 1–2 weeks",
    ROUTINE: "Discuss at your next routine check-up",
}


@dataclass(frozen=True)
class Guidance:
    """Interpretation of one feature value."""

    context: str
    recommendation: Optional[str] = None
    priority: str = ROUTINE
    abnormal: bool = True


@dataclass(frozen=True)
class Rule:
    """Reference range plus wording and escalation thresholds for a lab value."""

    low: float
    high: float
    unit: str = ""
    low_msg: str = ""
    low_rec: Optional[str] = None
    high_msg: str = ""
    high_rec: Optional[str] = None
    soon_low: Optional[float] = None
    urgent_low: Optional[float] = None
    soon_high: Optional[float] = None
    urgent_high: Optional[float] = None


def _fmt(number: float) -> str:
    return f"{number:g}"


def _evaluate_rule(rule: Rule, value: float) -> Guidance:
    reference = f"{_fmt(rule.low)}–{_fmt(rule.high)} {rule.unit}".strip()
    if rule.low <= value <= rule.high:
        return Guidance(
            f"Within the general reference range ({reference}).", abnormal=False
        )

    below = value < rule.low
    direction = "below" if below else "above"
    message = rule.low_msg if below else rule.high_msg
    recommendation = rule.low_rec if below else rule.high_rec

    priority = ROUTINE
    if below:
        if rule.urgent_low is not None and value < rule.urgent_low:
            priority = URGENT
        elif rule.soon_low is not None and value < rule.soon_low:
            priority = SOON
    else:
        if rule.urgent_high is not None and value > rule.urgent_high:
            priority = URGENT
        elif rule.soon_high is not None and value > rule.soon_high:
            priority = SOON

    context = f"Value is {direction} the general range ({reference}). {message}".strip()
    return Guidance(context, recommendation, priority)


# --------------------------------------------------------------------------- #
# Reference rules
# --------------------------------------------------------------------------- #

_LIVER_RULES: dict[str, Rule] = {
    "ALB": Rule(
        3.4, 5.4, "g/dL",
        low_msg="Low albumin can be associated with liver disease, kidney protein loss, chronic inflammation, or malnutrition.",
        low_rec="Ask your doctor about a full liver panel, a urine protein test, and a review of your nutrition (adequate protein and calories).",
        high_msg="High albumin most often reflects dehydration.",
        high_rec="Drink adequate fluids and repeat the test; discuss it if it stays high.",
        soon_low=3.0,
    ),
    "Alkphos": Rule(
        20, 130, "U/L",
        low_msg="Low alkaline phosphatase can occasionally be associated with malnutrition or zinc deficiency.",
        low_rec="Discuss a persistently low result with a doctor, along with your diet and any supplements you take.",
        high_msg="High alkaline phosphatase can be associated with bile-duct, liver, or bone conditions.",
        high_rec="Ask whether GGT and an abdominal ultrasound are needed to tell liver/bile-duct causes from bone causes.",
        soon_high=260,
    ),
    "Sgpt": Rule(
        4, 36, "U/L",
        low_msg="Low ALT is usually not a concern.",
        high_msg="High ALT can be associated with liver-cell injury, viral or alcohol-related hepatitis, fatty liver, or medicine/supplement effects.",
        high_rec="Avoid alcohol, review all medicines, herbal products and supplements with a doctor, and ask about hepatitis B/C tests and a liver ultrasound.",
        soon_high=108,
    ),
    "Sgot": Rule(
        8, 33, "U/L",
        low_msg="Low AST is usually not a concern.",
        high_msg="High AST can be associated with liver injury or muscle injury (for example after heavy exercise).",
        high_rec="Avoid alcohol and strenuous exercise before repeating the test, and ask about an AST/ALT comparison and a liver ultrasound.",
        soon_high=99,
    ),
    "TB": Rule(
        0.1, 1.2, "mg/dL",
        low_msg="Low bilirubin is usually not a concern.",
        high_msg="High bilirubin can be associated with jaundice, liver disease, bile-duct obstruction, or red-cell breakdown (hemolysis).",
        high_rec="Get this evaluated, with direct/indirect bilirubin split, especially if your skin or eyes look yellow, urine is dark, or stools are pale.",
        soon_high=2.0,
    ),
    "TP": Rule(
        6.0, 8.3, "g/dL",
        low_msg="Low total protein can be associated with liver or kidney disease, or malnutrition.",
        low_rec="Discuss diet, liver function, and a urine protein test with a doctor.",
        high_msg="High total protein can occur with dehydration or chronic inflammation.",
        high_rec="Drink adequate fluids and repeat the test; discuss it if it stays high.",
    ),
}

_KIDNEY_RULES: dict[str, Rule] = {
    "bu": Rule(
        7, 20, "mg/dL",
        low_msg="Low urea is usually not a concern and can reflect low protein intake or overhydration.",
        high_msg="High blood urea can reflect reduced kidney function, dehydration, high protein intake, or other medical causes.",
        high_rec="Ask for creatinine, eGFR and a urine albumin-to-creatinine ratio (uACR) to interpret this, and drink adequate fluids unless you have a fluid restriction.",
        soon_high=40,
    ),
    "sc": Rule(
        0.6, 1.3, "mg/dL",
        low_msg="Low creatinine can reflect low muscle mass or other factors.",
        low_rec="Discuss the result in its clinical context.",
        high_msg="High creatinine can indicate reduced kidney filtration or kidney injury.",
        high_rec="Ask for an eGFR calculation, a urine test (uACR and routine microscopy), and a repeat test in 1–3 months to see if it persists.",
        soon_high=1.5,
    ),
    "sod": Rule(
        135, 145, "mmol/L",
        low_msg="Low sodium can cause tiredness, headache, nausea or confusion.",
        low_rec="Get this checked promptly and avoid drinking excessive water without medical advice.",
        high_msg="High sodium usually reflects water loss or inadequate fluid intake.",
        high_rec="Get this checked and do not make drastic changes to salt or water intake on your own.",
        soon_low=130, urgent_low=125, soon_high=150, urgent_high=155,
    ),
    "pot": Rule(
        3.5, 5.0, "mmol/L",
        low_msg="Low potassium can cause weakness, cramps, or heart-rhythm changes.",
        low_rec="Discuss a medical assessment to find the cause, including diuretics, diarrhea or vomiting.",
        high_msg="High potassium can affect heart rhythm.",
        high_rec="Contact a clinician promptly; do not take potassium supplements or change medicines without advice, and ask which high-potassium foods to limit.",
        soon_low=3.2, urgent_low=2.8, soon_high=5.5, urgent_high=6.0,
    ),
    "sg": Rule(
        1.005, 1.030, "",
        low_msg="Low specific gravity can reflect dilute urine or reduced concentrating ability of the kidneys.",
        low_rec="Discuss persistent abnormalities with a clinician; this is not a diagnosis on its own.",
        high_msg="High specific gravity usually reflects concentrated urine from low fluid intake or glucose/protein in urine.",
        high_rec="Maintain adequate hydration unless you have a prescribed fluid restriction, and repeat the test.",
    ),
}


def _hemoglobin_rule(gender: Optional[int]) -> Rule:
    if gender == 1:
        low, high = 13.8, 17.2
    elif gender == 0:
        low, high = 12.1, 15.1
    else:
        low, high = 12.1, 17.2  # sex unknown: use the combined range
    return Rule(
        low, high, "g/dL",
        low_msg="Low hemoglobin (anemia) is common in kidney disease, but also with iron, B12 or folate deficiency and blood loss.",
        low_rec="Ask for an iron profile (ferritin, transferrin saturation), vitamin B12 and folate, and kidney tests.",
        high_msg="High hemoglobin can reflect dehydration, smoking, low oxygen levels, or other causes.",
        high_rec="Check hydration and discuss other causes with a clinician.",
        soon_low=10.0, urgent_low=7.0,
    )


# --------------------------------------------------------------------------- #
# Feature-specific guidance
# --------------------------------------------------------------------------- #

def _glucose_guidance(value: float) -> Guidance:
    note = (
        " Fasting status is not available, so this is read cautiously: "
        "fasting ≥126 mg/dL or random ≥200 mg/dL is in the diabetes range, and fasting 100–125 mg/dL is prediabetes."
    )
    if value >= 300:
        return Guidance(
            "Blood glucose is very high." + note,
            "Seek same-day medical care, and go to emergency care if you have extreme thirst, vomiting, abdominal pain, fast breathing or confusion.",
            URGENT,
        )
    if value >= 200:
        return Guidance(
            "Blood glucose is in a range that suggests diabetes if confirmed." + note,
            "See a doctor within 1–2 weeks for confirmatory testing (fasting glucose, HbA1c).",
            SOON,
        )
    if value >= 140:
        return Guidance(
            "Blood glucose is mildly elevated if this was a random sample." + note,
            "Confirm with a fasting glucose and HbA1c, and review the result with a clinician.",
            ROUTINE,
        )
    if value < 70:
        return Guidance(
            "Blood glucose is low (below 70 mg/dL), which can cause sweating, shakiness or confusion.",
            "Discuss the cause with a clinician, especially if you take diabetes medicines.",
            SOON,
        )
    return Guidance("Blood glucose is not clearly elevated." + note, abnormal=False)


def _bmi_guidance(value: float, age: Optional[int]) -> Guidance:
    if age is not None and age < 18:
        return Guidance(
            "Adult BMI cutoffs do not apply to patients under 18.",
            "Use an age-appropriate pediatric growth assessment with a clinician.",
        )
    if value < 18.5:
        return Guidance(
            "BMI is below the adult reference range and may indicate underweight or nutritional risk.",
            "Discuss nutrition, diet, and possible underlying causes with a clinician.",
        )
    if value < 23:
        return Guidance(
            "BMI is within the Asian Indian adult reference range (18.5–22.9 kg/m²).",
            abnormal=False,
        )
    if value < 25:
        return Guidance(
            "BMI is in the overweight range (23–24.9 kg/m²) under Asian Indian adult cutoffs.",
            "Aim for gradual weight loss of 5–7% through diet and at least 150 minutes of moderate activity per week.",
        )
    return Guidance(
        "BMI is in the obesity range (25 kg/m² or above) under Asian Indian adult cutoffs; excess abdominal fat raises insulin resistance.",
        "Discuss a structured weight-management plan (nutrition counselling, activity, and medical options if appropriate) with a clinician.",
        SOON if value >= 30 else ROUTINE,
    )


def _hba1c_guidance(value: float) -> Guidance:
    if value < 5.7:
        return Guidance("HbA1c is below the prediabetes threshold (5.7%).", abnormal=False)
    if value < 6.5:
        return Guidance(
            "HbA1c is in the prediabetes range (5.7–6.4%), meaning blood sugar has been higher than ideal over the past ~3 months.",
            "Prediabetes is often reversible: lose 5–7% of body weight if overweight, be active 150 min/week, cut sugary drinks and refined carbohydrates, and repeat HbA1c yearly (sooner if advised).",
            ROUTINE,
        )
    return Guidance(
        "HbA1c is in the diabetes range (6.5% or above); a confirmatory test is generally needed.",
        "See a physician within 1–2 weeks to confirm the diagnosis, and ask about lipid, kidney, eye and foot checks.",
        SOON,
    )


def _age_guidance(model_name: str, age: float) -> Optional[Guidance]:
    if model_name == "diabetes" and age >= 45:
        return Guidance(
            "Diabetes risk rises with age, particularly after 45.",
            "Have your HbA1c or fasting glucose checked at least yearly.",
        )
    if model_name == "kidney" and age >= 60:
        return Guidance(
            "Kidney function naturally declines with age, so older adults are screened more closely.",
            "Have eGFR and urine albumin (uACR) checked at least yearly, especially with diabetes or hypertension.",
        )
    return None


def _clinical_guidance(
    model_name: str,
    feature: str,
    value: Any,
    gender: Optional[int],
    age: Optional[int],
) -> Optional[Guidance]:
    """Return guidance for one feature, or None when nothing actionable applies."""
    if feature == "smoking_history":
        status = str(value).strip().casefold()
        if status in {"current", "ever"}:
            return Guidance(
                "Smoking is associated with higher risk of type 2 diabetes, cardiovascular and kidney disease.",
                "Ask a healthcare professional about evidence-based quit support (counselling, nicotine replacement or other medicines).",
                SOON,
            )
        if status in {"former", "not current"}:
            return Guidance(
                "A past smoking history is associated with a modestly higher metabolic and cardiovascular risk.",
                "Stay smoke-free and keep up regular health screening.",
            )
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None

    if feature in {"age", "Age"}:
        return _age_guidance(model_name, number)

    if model_name == "liver":
        rule = _LIVER_RULES.get(feature)
        return _evaluate_rule(rule, number) if rule else None

    if model_name == "diabetes":
        if feature == "bmi":
            return _bmi_guidance(number, age)
        if feature == "HbA1c_level":
            return _hba1c_guidance(number)
        if feature == "blood_glucose_level":
            return _glucose_guidance(number)
        if feature == "hypertension" and number == 1:
            return Guidance(
                "Reported hypertension often clusters with insulin resistance and raises cardiovascular risk.",
                "Keep blood pressure follow-up and treatment as directed; home BP monitoring can help.",
            )
        if feature == "heart_disease" and number == 1:
            return Guidance(
                "Reported heart disease shares risk factors with diabetes.",
                "Ask your cardiologist or physician about combined heart and diabetes risk management.",
            )
        return None

    if model_name == "kidney":
        if feature == "al":
            if number < 1:
                return Guidance("No albumin detected in urine.", abnormal=False)
            return Guidance(
                "Albumin in urine (dipstick grade ≥1) can indicate kidney damage, but this alone does not establish a diagnosis; fever, exercise or infection can cause temporary protein.",
                "Ask for a urine albumin-to-creatinine ratio (uACR) and eGFR; kidney damage is confirmed only if abnormal for more than 3 months.",
                SOON if number >= 2 else ROUTINE,
            )
        if feature == "bgr":
            return _glucose_guidance(number)
        if feature == "htn" and number == 1:
            return Guidance(
                "Reported hypertension is a leading cause and accelerator of kidney damage.",
                "Keep blood pressure within your doctor's target, limit salt (about 5 g/day or less) and do not change medicines based on this prediction.",
            )
        if feature == "dm" and number == 1:
            return Guidance(
                "Reported diabetes is a leading cause of kidney disease.",
                "Keep glucose and HbA1c within your doctor's target, have uACR and eGFR checked yearly, and do not change medicines based on this prediction.",
            )
        if feature == "hemo":
            return _evaluate_rule(_hemoglobin_rule(gender), number)
        rule = _KIDNEY_RULES.get(feature)
        return _evaluate_rule(rule, number) if rule else None

    return None


# --------------------------------------------------------------------------- #
# Condition-level plans
# --------------------------------------------------------------------------- #

_CONDITION_PLAN: dict[str, dict[str, Any]] = {
    "liver": {
        "name": "liver disease",
        "screening": "Keep a healthy weight, limit alcohol, and have liver tests rechecked as your doctor advises.",
        "follow_up_tests": [
            "Repeat liver function tests in 2–4 weeks, with GGT and INR",
            "Hepatitis B and hepatitis C blood tests",
            "Ultrasound of the abdomen (checks for fatty liver and bile-duct problems)",
            "Review of all medicines, herbal products and supplements",
        ],
        "lifestyle": [
            "Avoid alcohol completely until a doctor reviews your results",
            "Aim for gradual weight loss if overweight; fatty liver improves with 5–10% weight loss",
            "Choose a diet rich in vegetables, whole grains and pulses; limit fried, sugary and ultra-processed foods",
            "Do not exceed the labelled dose of paracetamol and avoid unsupervised herbal remedies",
            "Ask your doctor whether hepatitis A and B vaccination is appropriate for you",
        ],
        "urgent": [
            "Yellow skin or eyes, dark urine, or pale stools",
            "Severe abdominal pain or a swollen abdomen",
            "Vomiting blood or black stools",
            "Unusual drowsiness or confusion",
        ],
    },
    "diabetes": {
        "name": "diabetes",
        "screening": "Have blood sugar (fasting glucose or HbA1c) checked every 1–3 years, or yearly with risk factors.",
        "follow_up_tests": [
            "Fasting plasma glucose and repeat HbA1c to confirm",
            "Oral glucose tolerance test if your doctor advises it",
            "Lipid profile, blood pressure check, and kidney tests (eGFR, uACR)",
            "Dilated eye exam and foot exam if diabetes is confirmed",
        ],
        "lifestyle": [
            "Be active for at least 150 minutes per week (e.g. brisk walking), plus strength training twice a week",
            "Replace sugary drinks and refined carbohydrates with fibre-rich foods such as vegetables, pulses and whole grains",
            "Watch portion sizes of rice, roti and sweets, and do not skip meals",
            "Aim for 7–8 hours of sleep and manage stress",
            "Quit tobacco if you smoke",
        ],
        "urgent": [
            "Extreme thirst or very frequent urination together with vomiting or abdominal pain",
            "Fruity-smelling breath or fast, deep breathing",
            "Confusion, severe drowsiness or fainting",
            "Blood glucose above 300 mg/dL",
        ],
    },
    "kidney": {
        "name": "kidney disease",
        "screening": "If you have diabetes, hypertension or a family history, check eGFR and uACR at least once a year.",
        "follow_up_tests": [
            "eGFR (from serum creatinine) and urine albumin-to-creatinine ratio (uACR)",
            "Urine routine and microscopy",
            "Kidney ultrasound if advised",
            "Repeat testing after about 3 months, since kidney disease is confirmed only when abnormalities persist",
        ],
        "lifestyle": [
            "Keep blood pressure and blood sugar in your doctor's target range",
            "Limit salt to about 5 g/day and avoid heavily processed or pickled foods",
            "Stay hydrated unless you have a fluid restriction",
            "Avoid regular painkillers such as ibuprofen or diclofenac unless prescribed, and avoid unregulated herbal or ayurvedic products",
            "Quit tobacco and stay physically active",
        ],
        "urgent": [
            "Much less urine than usual",
            "Swelling of the face, legs or feet, or sudden weight gain",
            "Shortness of breath, chest pain, palpitations or marked muscle weakness",
            "Persistent vomiting or confusion",
        ],
    },
}


def _risk_band(probability: float) -> str:
    # Illustrative bands; calibrate against your validation data before use.
    if probability >= 0.8:
        return "high"
    if probability >= 0.5:
        return "elevated"
    if probability >= 0.2:
        return "moderate"
    return "low"


# --------------------------------------------------------------------------- #
# SHAP
# --------------------------------------------------------------------------- #

def _row_shap_values(model: Any, features: pd.DataFrame) -> np.ndarray:
    """Per-feature TreeSHAP contributions (log-odds) for the first row.

    XGBoost's native ``pred_contribs`` handles the model's serialized base
    score, which the ``shap`` package's XGBoost loader cannot parse for these
    models, so the ``shap`` dependency is not needed.
    """
    classes = list(model.classes_)
    class_index = classes.index(1) if 1 in classes else len(classes) - 1
    contributions = np.asarray(
        model.get_booster().predict(xgb.DMatrix(features), pred_contribs=True)
    )
    if contributions.ndim == 3:
        row_contributions = contributions[0, class_index]
    elif contributions.ndim == 2:
        row_contributions = contributions[0]
    else:
        raise ValueError(f"Unexpected TreeSHAP output shape: {contributions.shape}")

    values = row_contributions[:-1]  # last column is the bias term
    if len(values) != len(features.columns):
        raise ValueError("SHAP values do not match the model input features.")
    return np.asarray(values, dtype=float)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_explanation(
    model_name: str,
    model: Any,
    features: pd.DataFrame,
    predicted_class: int,
    class_probabilities: Mapping[str, float],
    gender: Optional[int] = None,
    age: Optional[int] = None,
    display_values: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Summarize risk, abnormal disease-increasing SHAP factors and next steps."""
    if model_name not in _CONDITION_PLAN:
        raise ValueError(f"Unknown model_name: {model_name!r}")

    plan = _CONDITION_PLAN[model_name]
    condition = plan["name"]
    shap_values = _row_shap_values(model, features)
    probability = float(class_probabilities["1"])
    disease_predicted = predicted_class == 1
    row = features.iloc[0]

    # 1. Interpret every feature once.
    interpreted: dict[str, tuple[Any, Guidance]] = {}
    for feature in features.columns:
        feature = str(feature)
        model_value = row[feature]
        if pd.isna(model_value):
            continue
        shown = (
            display_values[feature]
            if display_values and feature in display_values
            else model_value
        )
        if isinstance(shown, np.generic):
            shown = shown.item()
        guidance = _clinical_guidance(
            model_name,
            feature,
            shown if feature == "smoking_history" else model_value,
            gender,
            age,
        )
        if guidance is not None:
            interpreted[feature] = (shown, guidance)

    def describe(feature: str, shown: Any, guidance: Guidance) -> dict[str, Any]:
        return {
            "feature": feature,
            "label": _LABELS.get(feature, feature),
            "value": shown,
            "unit": _UNITS.get(feature, ""),
        }

    # 2. Top abnormal factors that pushed the model toward disease.
    ranked = sorted(
        (
            (idx, float(val))
            for idx, val in enumerate(shap_values)
            if np.isfinite(val) and val > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    possible_factors: list[dict[str, Any]] = []
    factor_guidance: list[tuple[str, Guidance]] = []
    for idx, contribution in ranked:
        feature = str(features.columns[idx])
        if feature not in interpreted:
            continue
        shown, guidance = interpreted[feature]
        if not guidance.abnormal:
            continue  # a normal value is not a risk factor
        possible_factors.append(
            {
                **describe(feature, shown, guidance),
                "clinical_association": guidance.context,
                "priority": guidance.priority,
                "model_contribution": round(contribution, 3),
            }
        )
        factor_guidance.append((feature, guidance))
        if len(possible_factors) == 3:
            break

    # 3. Safety alerts: dangerous values are surfaced regardless of SHAP ranking.
    safety_alerts = [
        {
            **describe(feature, shown, guidance),
            "message": guidance.context,
            "action": guidance.recommendation,
        }
        for feature, (shown, guidance) in interpreted.items()
        if guidance.abnormal and guidance.priority == URGENT
    ]

    # 4. Prioritized, de-duplicated recommendations (alerts first).
    candidates: list[tuple[str, str, str]] = []
    for alert in safety_alerts:
        if alert["action"]:
            candidates.append((alert["label"], alert["action"], URGENT))
    for feature, guidance in factor_guidance:
        if guidance.recommendation:
            candidates.append(
                (_LABELS.get(feature, feature), guidance.recommendation, guidance.priority)
            )
    candidates.sort(key=lambda item: _PRIORITY_RANK[item[2]])  # stable sort
    seen: set[str] = set()
    recommendations = []
    for label, text, priority in candidates:
        if text in seen:
            continue
        seen.add(text)
        recommendations.append(
            {
                "factor": label,
                "text": text,
                "priority": priority,
                "timeframe": _PRIORITY_TEXT[priority],
            }
        )

    # 5. Overall urgency and risk band.
    priorities = [a for a in (item["priority"] for item in possible_factors)]
    if safety_alerts:
        priorities.append(URGENT)
    urgency = min(priorities, key=_PRIORITY_RANK.__getitem__) if priorities else ROUTINE
    if disease_predicted and urgency == ROUTINE:
        urgency = SOON  # a positive prediction warrants clinician follow-up
    risk_level = _risk_band(probability)

    # 6. Summary text.
    if disease_predicted:
        summary = (
            f"Your results show a pattern associated with increased {condition} "
            f"risk (estimated probability: {probability:.1%}, {risk_level} risk). "
            "The findings below are possible clinical associations, not confirmed "
            "causes or a diagnosis."
        )
        if not possible_factors:
            summary += (
                " No single abnormal value stood out; the score reflects a "
                "combination of smaller factors."
            )
    else:
        summary = (
            f"Your results did not fall in the higher-risk pattern for {condition} "
            f"(estimated probability: {probability:.1%}, {risk_level} risk). This "
            "result cannot rule out disease, especially if you have symptoms or "
            "concerns."
        )
    if safety_alerts:
        summary += (
            " One or more values are in a range that needs prompt medical "
            "attention; see the safety alerts."
        )

    show_workup = disease_predicted or bool(possible_factors) or bool(safety_alerts)
    return {
        "condition": condition,
        "risk_level": risk_level,
        "urgency": urgency,
        "urgency_text": _PRIORITY_TEXT[urgency],
        "summary": summary,
        "safety_alerts": safety_alerts,
        "possible_factors": possible_factors,
        "recommendations": recommendations,
        "follow_up_tests": plan["follow_up_tests"] if show_workup else [plan["screening"]],
        "lifestyle": plan["lifestyle"],
        "seek_urgent_care_if": plan["urgent"],
        "limitation": (
            "These factors can be associated with disease but do not establish "
            "what caused your result. Reference ranges assume the listed units; "
            "confirm them against your lab report and discuss the result with a "
            "healthcare professional. Do not start, stop or change any medicine "
            "based on this report."
        ),
    }