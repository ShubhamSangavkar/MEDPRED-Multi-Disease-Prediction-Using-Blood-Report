
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from xgboost import XGBClassifier

from explainability import build_explanation


router = APIRouter(tags=["Kidney prediction"])

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "kidney_model.json"
FEATURE_ORDER = [
    "age",
    "sg",
    "al",
    "bgr",
    "bu",
    "sc",
    "sod",
    "pot",
    "hemo",
    "htn",
    "dm",
]
model = XGBClassifier()
try:
    model.load_model(str(MODEL_PATH))
except Exception as exc:
    raise RuntimeError(f"Could not load kidney XGBoost model at {MODEL_PATH}.") from exc

if model.feature_names_in_.tolist() != FEATURE_ORDER:
    raise RuntimeError(
        "Kidney XGBoost model features do not match the required feature order."
    )


class KidneyPredictionInput(BaseModel):
    age: int = Field(..., ge=1, le=120, description="Age in years")
    sg: Optional[float] = Field(None, ge=0, description="Specific gravity")
    al: Optional[float] = Field(None, ge=0, description="Urine albumin")
    bgr: Optional[float] = Field(None, ge=0, description="Blood glucose")
    bu: Optional[float] = Field(None, ge=0, description="Blood urea")
    sc: Optional[float] = Field(None, ge=0, description="Serum creatinine")
    sod: Optional[float] = Field(None, ge=0, description="Sodium")
    pot: Optional[float] = Field(None, ge=0, description="Potassium")
    hemo: float = Field(..., gt=0, description="Hemoglobin")
    htn: Optional[int] = Field(None, ge=0, le=1, description="Hypertension indicator")
    dm: Optional[int] = Field(None, ge=0, le=1, description="Diabetes indicator")
    gender: Optional[int] = Field(
        None,
        ge=0,
        le=1,
        description="Gender encoding used by the application; not a model feature",
    )


@router.post("/predict/kidney")
def predict_kidney(data: KidneyPredictionInput):
    """Predict kidney model class and return probabilities for each class."""
    missing_features = []
    feature_values = {}
    for feature_name in FEATURE_ORDER:
        value = getattr(data, feature_name)
        if value is None:
            value = float("nan")
            missing_features.append(feature_name)
        feature_values[feature_name] = value

    try:
        features = pd.DataFrame(
            [[feature_values[name] for name in FEATURE_ORDER]],
            columns=FEATURE_ORDER,
        )
        predicted_class = int(model.predict(features)[0])
        probabilities = model.predict_proba(features)[0]
        explanation = build_explanation(
            "kidney",
            model,
            features,
            predicted_class,
            {
                str(int(class_index)): float(probability)
                for class_index, probability in zip(model.classes_, probabilities)
            },
            gender=data.gender,
            display_values={
                name: "Yes" if getattr(data, name) == 1 else "No"
                for name in ("htn", "dm")
                if getattr(data, name) is not None
            },
        )

        return {
            "model": "kidney_xgboost",
            "predicted_class": predicted_class,
            "class_probabilities": {
                str(int(class_index)): round(float(probability), 6)
                for class_index, probability in zip(model.classes_, probabilities)
            },
            "missing_features": missing_features,
            "explanation": explanation,
            "note": (
                "Class 1 indicates disease and Class 0 indicates no disease. "
                "This machine-learning prediction is not a medical diagnosis."
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Kidney model prediction failed: {str(exc)}",
        ) from exc
