
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from xgboost import XGBClassifier

from explainability import build_explanation


router = APIRouter(tags=["Diabetes prediction"])

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "diabetes_model.json"
SMOKING_HISTORY_CODES = {
    "never": 0,
    "no info": 1,
    "current": 2,
    "former": 3,
    "ever": 4,
    "not current": 5,
}
FEATURE_ORDER = [
    "gender",
    "age",
    "smoking_history",
    "bmi",
    "HbA1c_level",
    "blood_glucose_level",
]

model = XGBClassifier()
try:
    model.load_model(str(MODEL_PATH))
except Exception as exc:
    raise RuntimeError(f"Could not load diabetes XGBoost model at {MODEL_PATH}.") from exc


class DiabetesPredictionInput(BaseModel):
    gender: int = Field(..., description="Numeric gender encoding used during training")
    age: int = Field(..., ge=1, le=120, description="Age in years")
    smoking_history: str = Field(..., description="Smoking history category")
    bmi: float = Field(..., gt=0, le=100, description="Body mass index")
    HbA1c_level: float = Field(..., gt=0, le=20, description="HbA1c level")
    blood_glucose_level: Optional[float] = Field(
        None,
        gt=0,
        description="Blood glucose",
    )


@router.post("/predict/diabetes")
def predict_diabetes(data: DiabetesPredictionInput):
    """Predict the diabetes model class and return probabilities for each class."""
    smoking_code = SMOKING_HISTORY_CODES.get(data.smoking_history.strip().casefold())
    if smoking_code is None:
        raise HTTPException(
            status_code=422,
            detail="smoking_history must be one of: Never, No Info, Current, Former, Ever, Not current.",
        )

    glucose_value = (
        float("nan")
        if data.blood_glucose_level is None
        else data.blood_glucose_level
    )

    try:
        features = pd.DataFrame(
            [[
                data.gender,
                data.age,
                smoking_code,
                data.bmi,
                data.HbA1c_level,
                glucose_value,
            ]],
            columns=FEATURE_ORDER,
        )
        predicted_class = int(model.predict(features)[0])
        probabilities = model.predict_proba(features)[0]
        explanation = build_explanation(
            "diabetes",
            model,
            features,
            predicted_class,
            {
                str(int(class_index)): float(probability)
                for class_index, probability in zip(model.classes_, probabilities)
            },
            age=data.age,
            display_values={
                "gender": "Male" if data.gender == 1 else "Female",
                "smoking_history": data.smoking_history,
            },
        )

        return {
            "model": "diabetes_xgboost",
            "predicted_class": predicted_class,
            "class_probabilities": {
                str(int(class_index)): round(float(probability), 6)
                for class_index, probability in zip(model.classes_, probabilities)
            },
            "missing_features": (
                ["blood_glucose_level"] if data.blood_glucose_level is None else []
            ),
            "explanation": explanation,
            "note": (
                "Class 1 indicates disease and Class 0 indicates no disease. "
                "This machine-learning prediction is not a medical diagnosis."
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Diabetes model prediction failed: {str(exc)}",
        ) from exc
