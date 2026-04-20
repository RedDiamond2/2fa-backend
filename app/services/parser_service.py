# app/services/parser_service.py

import re
import asyncio
import logging
from typing import List, Dict, Optional
from app.services.location_service import infer_location, LOCATION_DB
from app.services.confidence_service import compute_confidence
from app.services.context_service import build_context, get_conversation_history, save_conversation
from app.services.memory_service import enrich_with_memory
from app.services.learning_service import get_learning_cases
from app.services.warning_service import generate_warnings
from app.services.usage_service import log_event
from app.services.payment_service import detect_payment
from app.schemas.parser_schema import ParsedOrder, Item, Address
from app.utils.phone_utils import clean_phone
from app.services.learning_service import find_best_learning_match

logger = logging.getLogger("parser_service")

# ================================
# 🧠 Dictionaries & Constants
# ================================
NUMBER_MAP = {
    "واحد": 1, "وحدة": 1, "زوج": 2, "جوج": 2,
    "ثلاثة": 3, "ثلاث": 3, "اربعة": 4, "خمسة": 5,
    "ستة": 6, "سبعة": 7, "ثمانية": 8
}

PRODUCTS_MAP = {
    "تريكو": ["تريكو", "تيشرت", "تيش", "tshirt", "تيشورت", "تيشور"],
    "صباط": ["صباط", "حذاء", "شوز", "سباط"],
    "قميص": ["قميص", "شميز", "chemise"],
    "سروال": ["سروال", "جين", "جينز", "pantalon"],
    "فستان": ["فستان"]
}

COLORS = {
    "نوار": "أسود", "اسود": "أسود", "أبيض": "أبيض", "بيض": "أبيض",
    "حمر": "أحمر", "احمر": "أحمر", "جون": "أصفر", "اصفر": "أصفر",
    "ازرق": "أزرق", "أزرق": "أزرق"
}

SIZES = ["xs", "s", "m", "l", "xl", "xxl", "2xl", "3xl"]

NAME_STOPWORDS = [
    "السلام", "عليكم", "مرحبا", "نحب", "حاب", "نحتاج",
    "بغيت", "زيدني", "كاين", "واحد", "زوج", "خويا", "يا", "ألو"
]

IGNORE_NUM_CONTEXT = ["باب", "رقم", "بناية", "عمارة"]
CONTINUATION_WORDS = ["زيدني", "زيد", "حتى", "وزيد", "اضف"]

# ================================
# 🧹 Helpers
# ================================

def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return text

def safe_infer_location(text: str) -> Dict:
    try:
        return infer_location(text)
    except Exception as e:
        logger.error(f"LOCATION ERROR: {e}")
        return {}

# ================================
# 🧠 INTENT DETECTION
# ================================

def detect_intent(text: str) -> str:
    text = normalize(text)
    if any(w in text for w in ["بدل", "غير", "تغيير"]):
        return "update"
    if any(w in text for w in ["زيد", "اضف"]):
        return "add"
    if any(w in text for w in ["احذف", "نحي", "الغاء"]):
        return "remove"
    if any(w in text for w in ["نأكد", "أكد", "confirm"]):
        return "confirm"
    return "new"

# ================================
# 🔢 Logic Engines
# ================================

def classify_number(num_str: str) -> Dict:
    try:
        num = int(num_str)
    except:
        return {"type": "ignore", "value": None}

    if len(num_str) in [9, 10, 12]:
        return {"type": "phone", "value": clean_phone(str(num_str))}

    if 1 <= num <= 100: 
        return {"type": "quantity", "value": num}

    return {"type": "ignore", "value": None}

def extract_phone(text: str) -> Optional[str]:
    matches = re.findall(r"\d+", text)
    for m in matches:
        classified = classify_number(m)
        if classified["type"] == "phone":
            return classified["value"]
    return None

def smart_segment(text: str) -> Dict:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    result = {"phone": None, "name": None, "address": None, "items_text": None}
    items_lines, address_lines = [], []

    for i, line in enumerate(lines):
        clean = normalize(line)
        phone = extract_phone(clean)
        if phone:
            result["phone"] = phone
            if not result["name"]:
                name_candidate = extract_name(line)
                if name_candidate:
                    result["name"] = name_candidate
                else:
                    name_parts = [w for w in normalize(re.sub(r"\d+", " ", line)).split() if w not in NAME_STOPWORDS and not any(c.isdigit() for c in w)]
                    if 1 <= len(name_parts) <= 3:
                        result["name"] = " ".join(name_parts)
            continue

        words = clean.split()
        has_product = any(detect_product(w) for w in words)

        if not result["name"]:
            if len(words) <= 3 and not any(w.isdigit() for w in words):
                if not has_product and not any(w in NAME_STOPWORDS for w in words):
                    if i == 0 or len(lines) <= 3:
                        result["name"] = line
                        continue

        if has_product:
            items_lines.append(line)
            continue

        address_lines.append(line)

    result["items_text"] = " ".join(items_lines) if items_lines else None
    result["address"] = " ".join(address_lines) if address_lines else None
    return result

def extract_name(text: str) -> Optional[str]:
    match = re.search(r"^([^\d\n]+?)\s+0\d{9,11}", text.strip())
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:اسمي|انا|أنا|معاك)\s+([^\n\d]+)", text)
    if match: return match.group(1).strip()
    match = re.search(r"(?:الاسم[:：]?)\s*([^\n\d]+)", text)
    if match: return match.group(1).strip()
    words = text.split()
    filtered = [w for w in words if w not in NAME_STOPWORDS and not re.search(r"\d", w)]
    if 1 <= len(filtered) <= 3:
        return " ".join(filtered)
    return None

def detect_product(word: str) -> Optional[str]:
    """
    🔍 PRODUCT DETECTION with strict anti-corruption safeguards
    
    CRITICAL FIX: The old fuzzy matching allowed corrupted words to match.
    Example: "تريك" (corrupted) matched "تريكو" due to substring check.
    
    New logic:
    1. Exact match first (safest)
    2. Fuzzy match ONLY if word contains variant (not substring)
    3. Never allow substring match when it could be result of truncation
    """
    word = word.strip()
    if not word:
        return None
    
    for key, variants in PRODUCTS_MAP.items():
        # STEP 1: Exact match (highest priority)
        if word in variants:
            return key
        
        # STEP 2: Fuzzy match ONLY for reasonable variations
        # Protect against corrupted words like "تريك" matching "تريكو"
        for v in variants:
            # Only fuzzy match if:
            # - Word is long enough (len > 3)
            # - AND word is mostly contained (80%+ match)
            # - AND NOT a case where word is obvious truncation of variant
            if len(word) > 3 and len(v) > 3:
                # Prevent truncated matches: if variant starts with word + 1-2 chars, skip
                if v.startswith(word) and len(v) - len(word) <= 2:
                    # "تريك" starting "تريكو" → SKIP (corrupted truncation)
                    continue
                # Allow match if variant is fully contained in word or vice versa
                if word in v and len(word) / len(v) > 0.7:  # 70%+ overlap
                    return key
    
    return None

def extract_address(text: str) -> Dict:
    door = re.search(r"(?:باب|رقم باب)\s*(\d+)", text)
    building = re.search(r"(?:بناية|عمارة)\s*(\d+)", text)
    district, province = None, None
    for prov, data in (LOCATION_DB or {}).items():
        if re.search(rf"\b{re.escape(prov)}\b", text):
            province = prov
            for d in data.get("districts", []):
                if d in text:
                    district = d
                    break
            break
    return {"door": door.group(1) if door else None, "building": building.group(1) if building else None, "district": district, "province": province}

def extract_address_details(text: str) -> str:
    door = re.search(r"(?:باب|رقم باب)\s*(\d+)", text)
    building = re.search(r"(?:بناية|عمارة)\s*(\d+)", text)
    parts = []
    if door: parts.append(f"باب {door.group(1)}")
    if building: parts.append(f"بناية {building.group(1)}")
    return " - ".join(parts)

# ================================
# � PHASE 1: Safe Item Segmentation
# ================================

def segment_items_by_connector(text: str) -> List[str]:
    """
    🟢 PHASE 1: Safely segment items by "و" (AND) operator
    
    This function splits text into logical item chunks WITHOUT extracting attributes.
    Each segment is kept intact for later processing.
    
    Example:
    Input:  "3 تيشورت ابيض L و 2 سروال جينز ازرق XL"
    Output: ["3 تيشورت ابيض L", "2 سروال جينز ازرق XL"]
    
    Args:
        text: Raw item text containing potential segments
        
    Returns:
        List of item segments (one item per segment)
    """
    if not text:
        return []
    
    # 🔥 ROOT CAUSE FIX:
    # OLD PATTERN: \s+و(?:\s+|$) - matches و even when inside words like تريكو
    # Example: "2 تريكو ازرق" splits to ["2 تريك", "ازرق"] - CORRUPTS تريكو!
    # 
    # NEW PATTERN: \s+و\s+ - و must have SPACES BOTH BEFORE AND AFTER
    # This treats و as connector ONLY when standalone
    # Result: "2 تريكو ازرق" stays as ONE segment (no split)
    segments = re.split(r'\s+و\s+', text)
    
    # Clean and filter each segment
    cleaned_segments = []
    for segment in segments:
        cleaned = segment.strip()
        if cleaned:  # Only keep non-empty segments
            cleaned_segments.append(cleaned)
    
    return cleaned_segments

# ================================
# �📦 Item Extraction Engine
# ================================

def extract_items(text: str) -> List[Dict]:
    """
    🟢 PHASE 1: Extract items with safe segmentation by "و" (AND)
    
    Algorithm:
    1. Segment input by "و" first (PHASE 1)
    2. Process each segment independently to extract items
    3. Combine all extracted items
    
    This ensures attributes (color, size) stay with their products.
    """
    if not text:
        return []
    
    # 🟢 PHASE 1: Segment by "و" (AND operator)
    segments = segment_items_by_connector(text)
    
    if not segments:
        return []
    
    # Process each segment independently and collect items
    all_items = []
    previous_item = None
    
    for segment in segments:
        segment_items = _extract_items_from_segment(segment)
        
        if segment_items:
            # Normal case: segment produced items
            all_items.extend(segment_items)
            previous_item = segment_items[-1]  # Track last item for attribute attachment
        else:
            # 🔥 CRITICAL FIX: Segment has no product but might have attributes
            # Extract attributes from attribute-only segments and attach to previous item
            attr_only = _extract_attributes_only(segment)
            if attr_only and previous_item:
                # Attach color/size to the previous item if not already set
                if attr_only.get("color") and not previous_item.get("color"):
                    previous_item["color"] = attr_only["color"]
                if attr_only.get("size") and not previous_item.get("size"):
                    previous_item["size"] = attr_only["size"]
                # Don't add as separate item - just enrich previous one
    
    return all_items


def _extract_items_from_segment(text: str) -> List[Dict]:
    """
    🟡 PHASE 2: Extract single item per segment with proper attribute binding
    
    CRITICAL: Each segment produces EXACTLY ONE item with all attributes properly bound.
    This prevents item duplication and ensures attributes stay with their products.
    
    Algorithm:
    1. Extract quantity (leading number or word)
    2. Extract size keywords (XL, L, M, S, etc.)
    3. Extract color keywords (ابيض, اسود, ازرق, etc.)
    4. Build product name from remaining product-related words
    5. Return single item with all attributes
    
    Example:
    Input:  "2 سروال جينز ازرق XL"
    Output: [{"product": "سروال جينز", "quantity": 2, "color": "ازرق", "size": "XL"}]
    """
    if not text:
        return []
    
    normalized = normalize(text)
    words = normalized.split()
    
    if not words:
        return []
    
    # 🔥 DEBUG LOGGING (STEP 0)
    # Log to help diagnose future issues without breaking production
    debug_log = {
        "raw_text": text,
        "normalized": normalized,
        "words": words,
        "word_count": len(words)
    }
    
    # Initialize item structure
    item = {
        "product": None,
        "quantity": 1,
        "color": None,
        "size": None
    }
    
    # Track which word indices have been consumed by attributes
    used_indices = set()
    
    # ===== STEP 1: Extract Quantity =====
    # Check first word for quantity (e.g., "2" or "ثلاثة")
    if words[0].isdigit():
        qty_val = int(words[0])
        classified = classify_number(words[0])
        if classified["type"] == "quantity":
            item["quantity"] = qty_val
            used_indices.add(0)
    elif words[0] in NUMBER_MAP:
        item["quantity"] = NUMBER_MAP[words[0]]
        used_indices.add(0)
    
    # ===== STEP 2: Extract Size =====
    # Look for size keywords anywhere in the segment
    for i, w in enumerate(words):
        if w in SIZES:
            item["size"] = w.upper()
            used_indices.add(i)
            break  # One size per item
    
    # ===== STEP 3: Extract Color =====
    # Look for color keywords anywhere in the segment
    for i, w in enumerate(words):
        if w in COLORS:
            item["color"] = COLORS[w]
            used_indices.add(i)
            break  # One color per item
    
    # ===== STEP 4: Build Product Name =====
    # Collect remaining words that are product-related
    product_words = []
    for i, w in enumerate(words):
        # Skip words already consumed
        if i in used_indices:
            continue
        
        # Check if this word is a product variant
        if detect_product(w):
            product_words.append(w)
    
    # If we found product-related words, join them
    if product_words:
        item["product"] = " ".join(product_words)
    else:
        # No recognized product found in this segment
        return []
    
    # Guard against unreasonable quantities
    if item["quantity"] > 20:
        item["quantity"] = 20
    
    # 🔥 DEBUG LOGGING (STEP 5 - Final)
    debug_log["product"] = item["product"]
    debug_log["color"] = item["color"]
    debug_log["size"] = item["size"]
    debug_log["quantity"] = item["quantity"]
    # Silently log (don't print to avoid log spam in production)
    # But make available in meta if needed for debugging
    item["_debug"] = debug_log
    
    # ===== RETURN: Single item per segment =====
    return [item]

def _extract_attributes_only(text: str) -> Optional[Dict]:
    """
    🔥 CRITICAL FIX: Extract attributes from segments that have no product
    
    When segmentation fails and attributes end up in separate segments,
    this function extracts color/size so they can be attached to previous items.
    
    Example:
    Input: "ازرق 2XL" (no product, just attributes)
    Output: {"color": "أزرق", "size": "2XL"}
    
    Returns None if no attributes found.
    """
    if not text:
        return None
    
    normalized = normalize(text)
    words = normalized.split()
    
    if not words:
        return None
    
    attributes = {}
    
    # Extract size
    for w in words:
        if w in SIZES:
            attributes["size"] = w.upper()
            break
    
    # Extract color
    for w in words:
        if w in COLORS:
            attributes["color"] = COLORS[w]
            break
    
    # Only return if we found at least one attribute
    return attributes if attributes else None

def merge_similar_items(items: List[Dict]) -> List[Dict]:
    # 🔥 FIX 8: Guard against empty items
    if not items:
        return []
        
    merged = []
    for item in items:
        if item["quantity"] > 10: 
            item["quantity"] = 10  
        
        found = False
        for m in merged:
            same_attr = (m.get("color") == item.get("color") and m.get("size") == item.get("size"))
            if m.get("product") == item.get("product") and same_attr:
                m["quantity"] = min(10, m["quantity"] + item["quantity"])
                found = True
                break
        if not found:
            merged.append(item.copy())
    return merged

# ================================
# 🚀 Business Logic Utilities
# ================================

def split_orders(messages: List[str]) -> List[List[str]]:
    orders, current = [], []
    for msg in messages:
        msg = msg.strip()
        if not msg: continue
        current.append(msg)
        phone = extract_phone(normalize(msg))
        if phone and len(" ".join(current)) > 15:
            orders.append(current)
            current = []
    if current: orders.append(current)
    return orders
    
    

def apply_learning_boost(text: str, parsed: Dict) -> Dict:
    case = find_best_learning_match(text)

    if not case:
        return parsed

    corrected = case.get("corrected", {})

    # 🧠 SMART MERGE (NOT BLIND OVERRIDE)
    for k, v in corrected.items():
        if not v:
            continue

        # =========================
        # 🔥 ITEMS (SPECIAL LOGIC)
        # =========================
        if k == "items":
            if not parsed.get("items"):
                parsed["items"] = v
            else:
                try:
                    parsed_items = parsed.get("items", [])
                    learned_items = v

                    for li in learned_items:
                        for pi in parsed_items:
                            if pi.get("product") == li.get("product"):
                                pi["quantity"] = li.get("quantity")
                except Exception as e:
                    logger.error(f"[LEARNING][ITEM MERGE ERROR] {e}")

        # =========================
        # 🧠 NORMAL FIELDS (NEW 🔥)
        # =========================
        else:
            # override إذا فارغ أو غير موثوق
            if not parsed.get(k) or parsed.get(k) in ["⚠️", None, ""]:
                parsed[k] = v
            
    case["is_applied"] = True

    logger.info(f"[LEARNING][SMART_APPLIED] {case.get('raw_message')}")

    return parsed

# ================================
# 🏆 MAIN PARSER (V3 ULTRA PRO PLUS)
# ================================

async def parse_conversation(messages: List[str], conversation_id: Optional[str] = None, trace_id: Optional[str] = None) -> Dict:
    try:
        # 0. Anti-Spam & Pre-check
        messages = [str(m or "").strip() for m in messages if str(m or "").strip()]
        if len(messages) > 20: messages = messages[-20:]
        if not messages:
            return {"multi_orders": False, "order": {"status": "empty", "items": [], "meta": {}}}

        # =========================
        # 🔥 MULTI ORDER HANDLER
        # =========================
        batches = split_orders(messages)

        if len(batches) > 1:
            multi_results = await asyncio.gather(
                *[parse_conversation(b, None, trace_id) for b in batches],
                return_exceptions=True
            )

            valid_results = []
            for result in multi_results:
                if not isinstance(result, dict):
                    continue
                if result.get("multi_orders") is False and isinstance(result.get("order"), dict):
                    if result["order"].get("status") != "error":
                        valid_results.append(result["order"])
                elif result.get("multi_orders") is True and isinstance(result.get("orders"), list):
                    valid_results.extend([
                        order for order in result["orders"]
                        if isinstance(order, dict) and order.get("status") != "error"
                    ])

            if valid_results:
                return {"multi_orders": True, "orders": valid_results}

            return {
                "multi_orders": True,
                "orders": [{"status": "error", "items": [], "meta": {"error": "All orders failed"}}]
            }

        # =========================
        # 🧠 UNIQUE MESSAGE CLEANER
        # =========================
        seen, unique_messages = set(), []
        for m in messages:
            m = m.strip()
            if m and m not in seen:
                unique_messages.append(m)
                seen.add(m)

        history = get_conversation_history(conversation_id) if conversation_id else []
        context_text = build_context(unique_messages)
        full_context_text = context_text + " " + " ".join(history[-3:])
        
        # Intent Detection
        intent = detect_intent(" ".join(unique_messages))

        # 🔥 FIX 2: Context Leak Prevention (Added 'remove' to allowed history context)
        if intent in ["update", "add", "remove"]:
            context_for_parsing = full_context_text
        else:
            context_for_parsing = context_text

        context_msg = normalize(context_for_parsing)
        # 🧠 PRE-LEARNING BOOST (قبل أي parsing)
        pre_boost = find_best_learning_match(" ".join(messages))
        if pre_boost:
            logger.info(f"[LEARNING][PRE-BOOST] {pre_boost.get('raw_message')}")
        
        # 🧠 PRE-LEARNING INJECTION (REAL BOOST 🔥)
        case = find_best_learning_match(" ".join(messages))
        if case and case.get("corrected"):
            corrected = case["corrected"]

            # inject into context
            if corrected.get("items"):
                messages.append(str(corrected["items"]))
                
        # 3. Layered Extraction
        name, phone, address_details = None, None, None
        location_data, all_items = {}, []
        
        # SMART SEGMENTATION
        segmented = smart_segment("\n".join(unique_messages))
            
        for msg in unique_messages:
            try:
                clean_msg = normalize(msg)
                # 🔥 FIX 6: smart_segment name override protection
                if not name:
                    name = segmented.get("name") or name
                    if not name:
                        name = extract_name(" ".join(unique_messages))
                    if not name:
                        for line in unique_messages:
                            if len(line.split()) <= 2 and not any(c.isdigit() for c in line):
                                name = line.strip()
                                break
                
                if not phone: phone = segmented.get("phone") or extract_phone(clean_msg)
    
                address_input = segmented.get("address") or " ".join(unique_messages)
                details = extract_address_details(normalize(address_input))
                if details: address_details = details

                loc = safe_infer_location(clean_msg) or safe_infer_location(context_msg)
                if not loc: loc = safe_infer_location(" ".join(unique_messages))
                if loc:
                    for k, v in loc.items():
                        if v: location_data[k] = v

                addr_struct = extract_address(clean_msg)
                if any(addr_struct.values()):
                    for k, v in addr_struct.items():
                        if v: location_data[k] = v
            except Exception as e:
                logger.error(f"LOOP ERROR: {e}")

        # 🔥 FIX 3: Safe Phone fallback from history (limited to last 3)
        if not phone and history:
            for h in reversed(history[-3:]):
                p = extract_phone(normalize(h))
                if p:
                    phone = p
                    break
        
        # 4. Items Extraction
        # 🔥 FIX 7: Improved items_source selection
        items_source = segmented.get("items_text")
        if not items_source:
            items_source = " ".join([
                msg for msg in unique_messages
                if any(detect_product(w) for w in normalize(msg).split())
            ])
        
        if not items_source:
            items_source = "\n".join(unique_messages)
            
        all_items = extract_items(normalize(items_source))
        items = merge_similar_items(all_items)

        # 🔥 FIX 4: Secure Items history fallback (Intent restricted)
        items_from_history = False
        if not items and history and intent in ["update", "add"]:
            history_text = " ".join(history[-3:])
            fallback_items = extract_items(normalize(history_text))
            if fallback_items:
                items = merge_similar_items(fallback_items)
                items_from_history = True

        items = [i for i in items if i.get("product") and i.get("quantity", 0) > 0]
        if len(items) > 5: items = items[-5:]

        # 5. Build Parsed Object
        location = location_data.get("area") or location_data.get("district") or location_data.get("province")

        if not location:
            for line in unique_messages:
                if any(word in line for word in ["حي", "بلدية", "ولاية", "مسكن", "عمارة"]):
                    location = line
                    break

        if not location and segmented.get("address"):
            location = segmented.get("address")
        
        status = "needs_input"
        if items: status = "draft"
        if items and phone: status = "confirmed"
                
        parsed = {
            "intent": intent,
            "name": name,
            "phone": phone,
            "location": location,
            "address": {
                "full": segmented.get("address") or address_details or location_data.get("detail"),
                "province": location_data.get("province"),
                "district": location_data.get("district"),
                "area": location_data.get("area"),
                "building": location_data.get("building"),
                "door": location_data.get("door")
            },
            "items": items,
            "messages": [m for msg in unique_messages for m in msg.split("\n") if m.strip()],
            "status": status,
            "meta": {"items_from_history": items_from_history}
        }

        # 6. Payment & Memory & Learning
        full_text_raw = " ".join(unique_messages)
        payment = detect_payment(full_text_raw)
        if payment:
            parsed.update({"payment_type": payment.get("type"), "payment_value": payment.get("value"), "payment_status": "unpaid"})
        
        original_parsed = parsed.copy()
        parsed = enrich_with_memory(parsed) or parsed

        # Protect new data from memory overrides
        for field in ["name", "phone", "location"]:
            if original_parsed.get(field):
                parsed[field] = original_parsed[field]
                
        parsed = apply_learning_boost(full_text_raw, parsed) or parsed

        # 🧠 NEW: Track learning usage
        cases = get_learning_cases()
        for case in cases:
            if case.get("raw_message") and case["raw_message"] in full_text_raw:
                case["is_applied"] = True
        
        # 7. Confidence & Meta
        warnings = generate_warnings(parsed)
        confidence_data = compute_confidence(parsed)

        parsed.setdefault("meta", {})
        parsed["meta"].update({
            "confidence": confidence_data.get("confidence"),
            "decision": confidence_data.get("decision"),
            "breakdown": confidence_data.get("breakdown"),
            "field_confidence": confidence_data.get("field_confidence"),
            "warnings": warnings,
            "raw_items_count": len(all_items),
            "debug": {"intent": intent, "segmented": segmented, "items_source": items_source}
        })

        # 8. Production Logging
        log_event(
            event="parser_completed", trace_id=trace_id, conversation_id=conversation_id,
            status="ok", items_count=len(items), confidence=confidence_data.get("confidence"),
            decision=confidence_data.get("decision"),
            meta={"intent": intent, "has_name": bool(name), "has_phone": bool(phone)}
        )
            
        # =========================
        # 🔥 FALLBACK ENGINE
        # =========================
        if not parsed.get("items"):
            # 🔥 FIX 1: Fallback Crash Prevention
            full_text = messages[-1] if isinstance(messages[-1], str) else messages[-1].get("content", "")
            lines = [l.strip() for l in full_text.split("\n") if l.strip()]

            fallback_items = []
            fallback_name = parsed.get("name")
            fallback_phone = parsed.get("phone")
            fallback_location = parsed.get("location")

            for line in lines:
                if not fallback_phone and re.match(r"^0\d{9}$", line):
                    fallback_phone = clean_phone(line)
                    continue

                if not fallback_name and len(line.split()) <= 3 and not any(c.isdigit() for c in line):
                    fallback_name = line
                    continue

                match = re.match(r"(\d+)\s*(.+)", line)
                if match:
                    # 🔥 FIX 9: Product Detection in Fallback
                    qty = int(match.group(1))
                    product_detected = detect_product(match.group(2))
                    if product_detected:
                        fallback_items.append({"product": product_detected, "quantity": qty})
                    continue

                if not fallback_location:
                    fallback_location = line

            parsed.update({
                "name": fallback_name,
                "phone": fallback_phone,
                "location": fallback_location,
                "items": fallback_items or parsed.get("items")
            })

        # Final Schema Conversion
        parsed["address"] = Address(**parsed["address"])
        parsed["items"] = [Item(**item) for item in parsed["items"]]

        return {"multi_orders": False, "order": ParsedOrder(**parsed).model_dump()}

    except Exception as e:
        # 🔥 FIX 10: Error Logging
        log_event(event="parser_error", trace_id=trace_id, status="error", meta={"error": str(e)})
        print(f"❌ PARSER CRASH: {e}")
        logger.error(f"PARSER CRASH: {e}")
        return {
            "multi_orders": False,
            "order": {
                "status": "error",
                "items": [],
                "meta": {"error": str(e), "fallback": True}
            }
        }