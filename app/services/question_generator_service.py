# app/services/question_generator_service.py

from typing import Dict, Any, List
from uuid import uuid4


class CustomerQuestion:
    def __init__(
        self,
        question_id: str,
        message: str,
        field: str,
        priority: int = 1,
        meta: Dict[str, Any] = None,
    ):
        self.question_id = question_id
        self.message = message
        self.field = field
        self.priority = priority
        self.meta = meta or {}

    def to_dict(self):
        return {
            "question_id": self.question_id,
            "message": self.message,
            "field": self.field,
            "priority": self.priority,
            "meta": self.meta,
        }


class QuestionGeneratorService:

    # ==============================
    # MAIN ENTRY
    # ==============================
    def generate_customer_message(
        self,
        parsed_data: Dict[str, Any],
        conflicts: Dict[str, Any],
        confidence_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate ONE clean message to send to customer.
        """

        questions: List[CustomerQuestion] = []

        # 1. conflicts (أهم شيء)
        questions += self._generate_conflict_questions(conflicts)

        # 2. missing data
        questions += self._generate_missing_questions(parsed_data)

        # 3. low confidence (أقل أولوية)
        questions += self._generate_low_confidence_questions(confidence_data, parsed_data)

        # SORT
        questions.sort(key=lambda q: q.priority, reverse=True)

        # BUILD FINAL MESSAGE
        final_message = self._build_final_message(questions, parsed_data)

        return {
            "message": final_message,
            "questions": [q.to_dict() for q in questions]
        }

    # ==============================
    # FINAL MESSAGE BUILDER 🔥
    # ==============================
    def _build_final_message(
        self,
        questions: List[CustomerQuestion],
        parsed_data: Dict[str, Any]
    ) -> str:

        intro = "مرحبا 👋، نريد تأكيد طلبك من فضلك:\n\n"

        # Order summary (ذكي جدا)
        summary = self._build_order_summary(parsed_data)

        # Questions list
        body = ""
        for i, q in enumerate(questions, 1):
            body += f"{i}. {q.message}\n"

        outro = "\nشكراً لك 🙏"

        return intro + summary + body + outro

    def _build_order_summary(self, parsed_data: Dict[str, Any]) -> str:

        items = parsed_data.get("items", [])
        if not items:
            return ""

        text = "📦 الطلب:\n"

        for item in items:
            name = item.get("name", "")
            qty = item.get("quantity", 1)
            size = item.get("size")
            color = item.get("color")

            line = f"- {qty} x {name}"

            if size:
                line += f" | الحجم: {size}"
            if color:
                line += f" | اللون: {color}"

            text += line + "\n"

        return text + "\n"

    # ==============================
    # CONFLICT QUESTIONS
    # ==============================
    def _generate_conflict_questions(self, conflicts: Dict[str, Any]) -> List[CustomerQuestion]:

        questions = []

        for field, conflict in conflicts.items():

            if field == "items":
                for c in conflict:
                    questions.append(self._build_item_conflict_question(c))
            else:
                questions.append(self._build_field_conflict_question(field, conflict))

        return questions

    def _build_field_conflict_question(self, field: str, conflict: Dict[str, Any]) -> CustomerQuestion:

        field_labels = {
            "customer_name": "الاسم",
            "phone": "رقم الهاتف",
            "address": "العنوان"
        }

        label = field_labels.get(field, field)

        return CustomerQuestion(
            question_id=str(uuid4()),
            message=f"يرجى تأكيد {label} الصحيح.",
            field=field,
            priority=10,
            meta={
                "type": "conflict",
                "old": conflict.get("old"),
                "new": conflict.get("new")
            }
        )

    def _build_item_conflict_question(self, conflict: Dict[str, Any]) -> CustomerQuestion:

        product = conflict.get("product")
        conflict_type = conflict.get("type")

        if conflict_type == "quantity_conflict":
            msg = f"كم الكمية المطلوبة من ({product})؟"
        elif "size" in conflict_type:
            msg = f"ما هو الحجم الصحيح لمنتج ({product})؟"
        elif "color" in conflict_type:
            msg = f"ما هو اللون الصحيح لمنتج ({product})؟"
        else:
            msg = f"يرجى توضيح تفاصيل المنتج ({product})."

        return CustomerQuestion(
            question_id=str(uuid4()),
            message=msg,
            field="items",
            priority=10,
            meta=conflict
        )

    # ==============================
    # MISSING DATA
    # ==============================
    def _generate_missing_questions(self, parsed_data: Dict[str, Any]) -> List[CustomerQuestion]:

        questions = []

        if not parsed_data.get("customer_name"):
            questions.append(self._simple_q("ما هو اسمك؟", "customer_name", 9))

        if not parsed_data.get("phone"):
            questions.append(self._simple_q("يرجى إرسال رقم الهاتف.", "phone", 9))

        if not parsed_data.get("address"):
            questions.append(self._simple_q("يرجى إرسال العنوان الكامل.", "address", 9))

        if not parsed_data.get("items"):
            questions.append(self._simple_q("ما هي المنتجات المطلوبة؟", "items", 10))

        return questions

    # ==============================
    # LOW CONFIDENCE
    # ==============================
    def _generate_low_confidence_questions(
        self,
        confidence_data: Dict[str, Any],
        parsed_data: Dict[str, Any]
    ) -> List[CustomerQuestion]:

        questions = []
        threshold = 0.6

        for field, score in confidence_data.items():
            if score < threshold and parsed_data.get(field):

                value = parsed_data.get(field)

                questions.append(
                    CustomerQuestion(
                        question_id=str(uuid4()),
                        message=f"هل هذه المعلومة صحيحة: {value}؟",
                        field=field,
                        priority=6,
                        meta={"type": "low_confidence"}
                    )
                )

        return questions

    # ==============================
    # HELPERS
    # ==============================
    def _simple_q(self, text: str, field: str, priority: int) -> CustomerQuestion:
        return CustomerQuestion(
            question_id=str(uuid4()),
            message=text,
            field=field,
            priority=priority,
            meta={"type": "missing"}
        )


# Singleton
question_generator_service = QuestionGeneratorService()