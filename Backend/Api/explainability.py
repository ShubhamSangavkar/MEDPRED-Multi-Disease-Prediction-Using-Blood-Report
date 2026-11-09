from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
import xgboost as xgb


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
    "sc": "mg/dL",
    "sod": "mmol/L",
    "pot": "mmol/L",
    "hemo": "g/dL",
}


def _row_shap_values(
    model: Any,
    features: pd.DataFrame,
) -> np.ndarray:
    class_index = list(model.classes_).index(1)
    # XGBoost TreeSHAP handles the model's serialized base score; SHAP's current
    # XGBoost loader cannot parse the vector-valued base score in these models.
    contributions = np.asarray(
        model.get_booster().predict(
            xgb.DMatrix(features),
            pred_contribs=True,
        )
    )
    if contributions.ndim == 3:
        row_contributions = contributions[0, class_index]
    elif contributions.ndim == 2:
        row_contributions = contributions[0]
    else:
        raise ValueError(f"Unexpected TreeSHAP output shape: {contributions.shape}")

    values = row_contributions[:-1]
    # The API only needs the per-feature contribution values. Constructing a
    # shap.Explanation object adds a heavy optional dependency without changing
    # the JSON response, so keep the NumPy values directly.
    if len(values) != len(features.columns):
        raise ValueError("SHAP values do not match the model input features.")
    return np.asarray(values)


def _clinical_guidance(
    model_name: str,
    feature: str,
    value: Any,
    gender: Optional[int],
    age: Optional[int],
) -> tuple[Optional[str], Optional[str]]:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        if model_name == "diabetes" and feature == "smoking_history":
            if str(value).strip().casefold() == "current":
                return (
                    "Smoking is associated with higher risk of type 2 diabetes and cardiovascular disease.",
                    "If you smoke, discuss evidence-based support to quit with a healthcare professional.",
                )
        return None, None

    if model_name == "liver":
        ranges = {
            "ALB": (3.4, 5.4),
            "Alkphos": (20, 130),
            "Sgpt": (4, 36),
            "Sgot": (8, 33),
            "TB": (0.1, 1.2),
            "TP": (6.0, 8.3),
        }
        if feature not in ranges:
            return None, None
        low, high = ranges[feature]
        units = {
            "ALB": "g/dL",
            "Alkphos": "U/L",
            "Sgpt": "U/L",
            "Sgot": "U/L",
            "TB": "mg/dL",
            "TP": "g/dL",
        }
        reference = f"{low}–{high} {units[feature]}"
        if low <= numeric_value <= high:
            return f"This value is within the supplied general reference range ({reference}).", None
        range_context = (
            f"Value is {'below' if numeric_value < low else 'above'} the supplied "
            f"general range ({reference}). "
        )
        if feature == "ALB" and numeric_value < low:
            return (
                range_context + "Low albumin can be associated with liver disease, kidney protein loss, or malnutrition.",
                "Discuss liver and kidney assessment and nutritional status with a doctor.",
            )
        if feature == "ALB":
            return (
                range_context + "High albumin may occur with dehydration.",
                "Discuss a persistently high result with a doctor, especially if dehydration is not likely.",
            )
        if feature == "Alkphos" and numeric_value > high:
            return (
                range_context + "High alkaline phosphatase can be associated with bile duct, liver, or bone conditions.",
                "Discuss evaluation of liver, bile duct, and bone-related causes with a doctor.",
            )
        if feature == "Alkphos":
            return (
                range_context + "Low alkaline phosphatase can sometimes be associated with malnutrition or zinc deficiency.",
                "Discuss a persistently low result with a doctor.",
            )
        if feature == "Sgpt" and numeric_value > high:
            return (
                range_context + "High ALT can be associated with liver cell injury, hepatitis, or fatty liver.",
                "Avoid alcohol and review medicines with a doctor; discuss evaluation for possible liver injury.",
            )
        if feature == "Sgpt":
            return range_context + "Low ALT usually has no significant concern.", None
        if feature == "Sgot" and numeric_value > high:
            return (
                range_context + "High AST can be associated with liver or muscle injury.",
                "Discuss evaluation of liver and muscle-related causes with a doctor.",
            )
        if feature == "Sgot":
            return range_context + "Low AST usually has no significant concern.", None
        if feature == "TB" and numeric_value > high:
            return (
                range_context + "High bilirubin can be associated with jaundice, liver disease, bile duct obstruction, or hemolysis.",
                "Seek medical evaluation, especially if the skin or eyes look yellow.",
            )
        if feature == "TB":
            return range_context + "Low bilirubin usually has no significant concern.", None
        if feature == "TP" and numeric_value < low:
            return (
                range_context + "Low total protein can be associated with liver or kidney disease, or malnutrition.",
                "Discuss diet, liver function, and possible kidney protein loss with a doctor.",
            )
        if feature == "TP":
            return (
                range_context + "High total protein can occur with dehydration or chronic inflammation.",
                "Discuss a persistently high result with a doctor.",
            )
        return range_context.rstrip(), None

    if model_name == "diabetes":
        if feature == "bmi":
            if age is not None and age < 18:
                return (
                    "Adult BMI cutoffs do not apply to patients under 18.",
                    "Use an age-appropriate pediatric assessment with a clinician.",
                )
            if numeric_value < 18.5:
                return (
                    "BMI is below the adult reference range of 18.5–22.9 kg/m² and may indicate underweight or nutritional risk.",
                    "Discuss nutrition, diet, and possible underlying causes with a clinician.",
                )
            if numeric_value < 23:
                return "BMI is within the supplied Asian Indian adult reference range.", None
            if numeric_value < 25:
                return (
                    "BMI is in the overweight range (23–24.9 kg/m²) under common Asian Indian adult cutoffs.",
                    "Consider regular physical activity, a balanced diet, and weight management.",
                )
            return (
                "BMI is in the obesity range (25 kg/m² or above) under common Asian Indian adult cutoffs.",
                "Discuss a structured, medically appropriate weight-management plan with a clinician.",
            )
        if feature == "HbA1c_level":
            if numeric_value < 5.7:
                return "HbA1c is below the prediabetes threshold.", None
            if numeric_value < 6.5:
                return (
                    "HbA1c is in the prediabetes range (5.7–6.4%).",
                    "Discuss follow-up with a physician; consider reducing refined sugar, increasing activity, and monitoring glucose.",
                )
            return (
                "HbA1c is in the diabetes range (6.5% or above); confirmation is generally needed.",
                "Consult a physician to confirm the result and discuss appropriate diabetes management.",
            )
        if feature == "blood_glucose_level":
            return (
                "Fasting status is not available, so fasting glucose ranges cannot be applied safely.",
                "Confirm whether the sample was fasting and review the result with a clinician.",
            )
        return None, None

    if model_name == "kidney":
        if feature == "al":
            return (
                "Urine albumin can be associated with kidney damage, but this value alone does not establish a diagnosis.",
                "Discuss the result with a clinician, who may recommend a urine albumin-to-creatinine ratio (uACR) and eGFR assessment.",
            )
        if feature == "bu":
            return (
                "Abnormal blood urea can be associated with kidney function changes, dehydration, or other medical causes.",
                "Discuss this result alongside creatinine, eGFR, and the reference range provided by your laboratory.",
            )
        if feature == "bgr":
            return (
                "Fasting status is not available, so fasting glucose ranges cannot be applied safely.",
                "Confirm whether the sample was fasting and review the result with a clinician.",
            )
        if feature == "htn" and numeric_value == 1:
            return (
                "Reported hypertension contributed to the model score.",
                "Continue blood-pressure follow-up and treatment as directed by your clinician; do not change medicines based on this prediction.",
            )
        if feature == "dm" and numeric_value == 1:
            return (
                "Reported diabetes contributed to the model score.",
                "Continue diabetes follow-up as directed by your clinician; do not change medicines based on this prediction.",
            )
        if feature == "sg":
            if numeric_value > 1.030:
                return (
                    "Specific gravity is above the supplied general range (1.005–1.030) and can reflect concentrated urine; it is not a direct kidney diagnosis.",
                    "Discuss persistent abnormalities; maintain appropriate hydration unless you have a prescribed fluid restriction.",
                )
            if numeric_value < 1.005:
                return (
                    "Specific gravity is below the supplied general range (1.005–1.030) and can reflect dilute urine or reduced concentrating ability.",
                    "Discuss persistent abnormalities with a clinician.",
                )
        if feature == "sc":
            if numeric_value > 1.3:
                return (
                    "Creatinine is above the supplied general range (0.6–1.3 mg/dL) and may be associated with reduced kidney filtration or kidney injury.",
                    "Ask a doctor about eGFR and kidney-function assessment.",
                )
            if numeric_value < 0.6:
                return (
                    "Creatinine is below the supplied general range (0.6–1.3 mg/dL); low values can be associated with low muscle mass or other factors.",
                    "Discuss the result in its clinical context.",
                )
        if feature == "sod":
            if numeric_value > 145:
                return (
                    "Sodium is above the supplied general range (135–145 mmol/L).",
                    "Seek medical evaluation; do not make drastic changes to salt or water intake on your own.",
                )
            if numeric_value < 135:
                return (
                    "Sodium is below the supplied general range (135–145 mmol/L).",
                    "Seek medical evaluation and avoid excessive water intake without medical advice.",
                )
        if feature == "pot":
            if numeric_value > 5.0:
                return (
                    "Potassium is above the supplied general range (3.5–5.0 mmol/L); high levels can affect heart rhythm.",
                    "Contact a clinician promptly; do not self-treat or change medicines without advice.",
                )
            if numeric_value < 3.5:
                return (
                    "Potassium is below the supplied general range (3.5–5.0 mmol/L).",
                    "Discuss medical assessment and correction of the underlying cause with a clinician.",
                )
        if feature == "hemo" and gender in (0, 1):
            low, high = (13.8, 17.2) if gender == 1 else (12.1, 15.1)
            if numeric_value < low:
                return (
                    f"Hemoglobin is below the supplied sex-specific range ({low}–{high} g/dL).",
                    "Discuss assessment for iron, vitamin B12, folate deficiency, bleeding, and kidney-related causes.",
                )
            if numeric_value > high:
                return (
                    f"Hemoglobin is above the supplied sex-specific range ({low}–{high} g/dL).",
                    "Discuss hydration, oxygen levels, and other possible causes with a clinician.",
                )
        return None, None

    return None, None


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
    """Summarize medically relevant, disease-increasing SHAP factors."""
    shap_values = _row_shap_values(model, features)
    probability = float(class_probabilities["1"])
    disease_predicted = predicted_class == 1
    ranked_features = sorted(
        (
            (index, float(value))
            for index, value in enumerate(shap_values)
            if value > 0
            and np.isfinite(value)
            and not pd.isna(features.iloc[0, index])
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    possible_factors = []
    recommendations = []
    for index, _ in ranked_features:
        feature = str(features.columns[index])
        model_value = features.iloc[0, index]
        value = (
            display_values[feature]
            if display_values and feature in display_values
            else model_value
        )
        if isinstance(value, np.generic):
            value = value.item()

        context, recommendation = _clinical_guidance(
            model_name,
            feature,
            value if feature == "smoking_history" else model_value,
            gender,
            age,
        )
        if context is None:
            continue
        possible_factors.append(
            {
                "feature": feature,
                "label": _LABELS.get(feature, feature),
                "value": value,
                "unit": _UNITS.get(feature, ""),
                "clinical_association": context,
            }
        )
        if recommendation:
            recommendations.append(
                {"factor": _LABELS.get(feature, feature), "text": recommendation}
            )
        if len(possible_factors) == 3:
            break

    condition = {
        "liver": "liver disease",
        "diabetes": "diabetes",
        "kidney": "kidney disease",
    }[model_name]
    if disease_predicted:
        summary = (
            f"Your results show a pattern associated with increased {condition} "
            f"risk (estimated probability: {probability:.1%}). The findings below "
            "are possible clinical associations, not confirmed causes or a diagnosis."
        )
    else:
        summary = (
            f"Your results did not fall in the higher-risk pattern for {condition} "
            f"(estimated probability: {probability:.1%}). This result cannot rule "
            "out disease, especially if you have symptoms or concerns."
        )

    return {
        "condition": condition,
        "summary": summary,
        "possible_factors": possible_factors,
        "recommendations": recommendations,
        "limitation": (
            "These factors can be associated with disease but do not establish "
            "what caused your result. Reference ranges assume the listed units; "
            "confirm them against your lab report and discuss the result with a "
            "healthcare professional."
        ),
    }
