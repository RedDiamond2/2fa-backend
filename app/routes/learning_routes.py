# app/routes/learning_routes.py

from fastapi import APIRouter
from app.services.learning_service import store_learning_case

router = APIRouter()

@router.post("/learning/feedback")
def learning_feedback(data: dict):
    return store_learning_case(
        raw_message=data.get("raw_message"),
        parsed=data.get("parsed"),
        corrected=data.get("corrected"),
        confidence=data.get("confidence", 0.0)
    )