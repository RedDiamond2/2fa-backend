# app/models/comment_model.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Reply(BaseModel):
    id: str
    name: str
    text: str
    created_at: datetime

class Comment(BaseModel):
    id: str
    name: str
    text: str
    likes: int = 0
    liked_by: List[str] = []
    replies: List[Reply] = []
    created_at: datetime
    order_id: Optional[str] = None  # 🔗 Associate comment with order