

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from xgboost import XGBClassifier

from explainability import build_explanation


router = APIRouter(tags=["Liver prediction"])

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "liver_model.json"

model = XGBClassifier()
try:
    model.load_model(str(MODEL_PATH))
except Exception as exc:
    raise RuntimeError(
        f"Could not load XGBoost model at {MODEL_PATH}. "
        "Place liver_model.json beside liver_api.py."
    ) from exc


class LiverPredictionInput(BaseModel):
    Age: int = Field(..., ge=1, le=120, description="Age in years")
    Gender: int = Field(..., description="Numeric gender encoding used during training")
    ALB: Optional[float] = Field(None, description="Albumin")
    Alkphos: Optional[float] = Field(None, description="Alkaline phosphatase")
    Sgpt: Optional[float] = Field(None, description="SGPT / ALT")
    Sgot: Optional[float] = Field(None, description="SGOT / AST")
    TB: Optional[float] = Field(None, description="Total bilirubin")
    TP: Optional[float] = Field(None, description="Total protein")


@router.post("/predict/liver")
def predict_liver(data: LiverPredictionInput):
    """Predict the model class and return probabilities for both classes."""
    lab_features = ("ALB", "Alkphos", "Sgpt", "Sgot", "TB", "TP")
    missing_features = [
        feature_name
        for feature_name in lab_features
        if getattr(data, feature_name) is None
    ]
    try:
        features = pd.DataFrame(
            [[
                data.Age,
                data.Gender,
                *(
                    float("nan") if getattr(data, name) is None else getattr(data, name)
                    for name in lab_features
                ),
            ]],
            columns=["Age", "Gender", "ALB", "Alkphos", "Sgpt", "Sgot", "TB", "TP"],
        )

        predicted_class = int(model.predict(features)[0])
        probabilities = model.predict_proba(features)[0]
        explanation = build_explanation(
            "liver",
            model,
            features,
            predicted_class,
            {
                str(int(class_index)): float(probability)
                for class_index, probability in zip(model.classes_, probabilities)
            },
            display_values={
                "Gender": "Male" if data.Gender == 1 else "Female"
            },
        )

        return {
            "model": "liver_xgboost",
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
            detail=f"Liver model prediction failed: {str(exc)}",
        ) from exc


"""
Liver XGBoost prediction router for FastAPI.

Keep liver_model.json in the same directory as this file.
The model expects these features in this exact order:
Age, Gender, ALB, Alkphos, Sgpt, Sgot, TB, TP

IMPORTANT:
- Gender must use the same numeric encoding used during model training.
- Class 1 represents disease and Class 0 represents no disease.
"""