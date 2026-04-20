# app/services/learning_service.py

from datetime import datetime
from app.core.database import generate_id

# 🧠 in-memory (لاحقاً MongoDB)
learning_db = {}
# 🧠 NEW: index for fast lookup
learning_index = {}

def store_learning_case(raw_message: str, parsed: dict, corrected: dict, confidence: float):
    case_id = generate_id()
    key = raw_message.strip().lower()
    learning_index[key] = case_id

    learning_db[case_id] = {
        "id": case_id,
        "raw_message": raw_message,
        "parsed": parsed,
        "corrected": corrected,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),  # ✅ FIX

        # 🧠 Learning Fields (NEW)
        "source": "developer",
        "fields_fixed": list(corrected.keys()),
        "is_applied": False,
        "pattern": {}
    }
    return learning_db[case_id]


def find_best_learning_match(text: str):
    text = text.lower().strip()

    best_case = None
    best_score = 0

    for key, case_id in learning_index.items():
        key_norm = key.strip()

        # 🧠 simple similarity
        overlap = len(set(text.split()) & set(key_norm.split()))
        score = overlap / max(len(text.split()), 1)

        if score > best_score and score > 0.5:
            best_score = score
            best_case = learning_db.get(case_id)

    return best_case
    
def get_learning_cases():
    return list(learning_db.values())
    
    
def mark_case_as_applied(case_id: str):
    if case_id in learning_db:
        learning_db[case_id]["is_applied"] = True