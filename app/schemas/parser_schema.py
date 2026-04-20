# app/schemas/parser_schema.py

from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class Item(BaseModel):
    product: str
    quantity: int
    color: Optional[str] = None
    size: Optional[str] = None


class Address(BaseModel):
    full: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    area: Optional[str] = None
    building: Optional[str] = None
    door: Optional[str] = None


class ParsedOrder(BaseModel):
    intent: str
    name: Optional[str] = None
    phone: Optional[str] = None
    # Deprecated: location field is legacy and may contain a string or object.
    # Use address.full / address structure as the source of truth.
    location: Optional[str] = None
    address: Address
    items: List[Item]
    messages: List[str]
    status: str
    meta: Dict[str, Any]
    payment_type: Optional[str] = None
    payment_value: Optional[float] = None
    payment_status: Optional[str] = None