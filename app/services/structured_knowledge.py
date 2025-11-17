"""Structured knowledge base loader for domain-specific data.

Supports both unstructured text (for RAG) and structured data (for queries).
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from loguru import logger


class StructuredKnowledge:
    """Container for structured domain knowledge."""

    def __init__(self, data: Dict[str, Any]):
        """Initialize with structured data dictionary."""
        self.data = data
        self.id = data.get("id", "unknown")

    def get(self, path: str, default: Any = None) -> Any:
        """Get value from nested dictionary using dot notation.

        Args:
            path: Dot-separated path (e.g., "mobility.speed.max_speed_road_kmh")
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        keys = path.split(".")
        value = self.data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_context_text(self, language: str = "ar") -> str:
        """Get full context text for RAG.

        Args:
            language: Language code ("ar" or "en")

        Returns:
            Full context text in requested language
        """
        key = f"context_text_{language}"
        return self.data.get(key, "")

    def query_numeric(self, field_path: str) -> Optional[float]:
        """Query numeric field with type safety.

        Args:
            field_path: Dot path to numeric field

        Returns:
            Float value or None
        """
        value = self.get(field_path)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def format_answer(self, field_path: str, question_ar: str) -> str:
        """Format a structured answer to a question.

        Args:
            field_path: Path to the data field
            question_ar: Original question in Arabic

        Returns:
            Formatted answer in Arabic
        """
        value = self.get(field_path)

        if value is None:
            return f"عذراً، لا توجد معلومات متاحة عن هذا السؤال في قاعدة البيانات."

        # Format based on type
        if isinstance(value, (int, float)):
            return f"{value}"
        elif isinstance(value, str):
            return value
        elif isinstance(value, list):
            if all(isinstance(x, str) for x in value):
                return "، ".join(value)
            return str(value)
        else:
            return str(value)


class M1A1AbramsKnowledge(StructuredKnowledge):
    """Specialized knowledge class for M1A1 Abrams tank."""

    def __init__(self):
        """Initialize with M1A1 Abrams data."""
        data = {
            "id": "m1a1_abrams",
            "names": {
                "ar": "دبابة القتال الرئيسية إم1 إيه1 أبرامز",
                "en": "M1A1 Abrams Main Battle Tank"
            },
            "category": "main_battle_tank",
            "generation": 3,

            # Mobility data
            "mobility": {
                "engine": {
                    "type": "Gas turbine, multi-fuel",
                    "model": "Honeywell AGT1500",
                    "power_hp": 1500,
                    "fuel_types_ar": ["ديزل", "كيروسين طيران", "بنزين", "سولار بحري"]
                },
                "speed": {
                    "max_speed_road_kmh": 67.0,
                    "max_speed_offroad_kmh": 48.0
                },
                "range": {
                    "without_nbc_km": 465.0,
                    "with_nbc_km": 448.9
                }
            },

            # Dimensions
            "dimensions": {
                "length_m": 9.8,
                "width_m": 3.65,
                "height_m": 2.375,
                "ground_clearance_m": 0.48,
                "combat_weight_tons": 63
            },

            # Armament
            "armament": {
                "main_gun": {
                    "caliber_mm": 120,
                    "model": "M256",
                    "type_ar": "مدفع أملس السبطانة",
                    "ammo_rounds": 40
                },
                "machine_guns": {
                    "commander_mg_rounds": 1000,
                    "total_762_rounds": 12400
                },
                "smoke_grenades": 24
            },

            # Crew
            "crew": {
                "size": 4,
                "roles_ar": ["القائد", "الرامي", "المعمر", "السائق"]
            },

            # Full context text for RAG
            "context_text_ar": """
دبابة القتال الرئيسية إم1 إيه1 أبرامز هي دبابة من الجيل الثالث، تم تطويرها في الولايات المتحدة ويتم تجميعها أيضاً في جمهورية مصر العربية داخل منشآت الهيئة العربية للتصنيع.
تتميز الدبابة بمحرك توربيني غازي متعدد الوقود بقوة 1500 حصان، مع ناقل حركة هيدروكيناتيكي أوتوماتيكي بأربع سرعات أمامية وسرعتين خلفيتين، ما يمنحها قدرة عالية على المناورة
وسرعة قصوى تقارب 67 كم/ساعة على الطرق الممهدة وحوالي 48 كم/ساعة على الطرق غير الممهدة، مع مدى تشغيلي يصل إلى حوالي 465 كم بدون تشغيل أجهزة الوقاية من أسلحة الدمار الشامل NBC
وحوالي 449 كم مع تشغيل هذه الأجهزة.

التسليح الرئيسي للدبابة هو مدفع أملس السبطانة عيار 120 مم طراز M256، مع حمولة تصل إلى 40 طلقة. تسليحها الثانوي يشمل رشاش القائد عيار 12.7 مم طراز M2 مع 1000 طلقة،
ورشاشين عيار 7.62 مم طراز M240 بإجمالي حوالي 12,400 طلقة. الوزن القتالي حوالي 63 طن، والطول الكلي مع توجيه المدفع للأمام حوالي 9.8 متر، والعرض حوالي 3.65 متر.

يتكون طاقم إم1 إيه1 من أربعة أفراد: القائد، الرامي، المعمر، والسائق، وهم يعملون معاً لتشغيل الدبابة بكفاءة عالية في مهام الهجوم والدفاع ومساندة القوات البرية.
"""
        }

        super().__init__(data)

    def answer_question(self, question: str) -> Optional[str]:
        """Answer common questions about M1A1 using structured data.

        Args:
            question: Question in Arabic

        Returns:
            Answer string or None if cannot be answered from structured data
        """
        question_lower = question.lower()

        # Speed questions
        if any(word in question_lower for word in ["سرعة", "سريع", "speed"]):
            if "طرق" in question_lower or "ممهد" in question_lower:
                speed = self.query_numeric("mobility.speed.max_speed_road_kmh")
                return f"السرعة القصوى على الطرق الممهدة هي {speed} كم/ساعة"
            else:
                road = self.query_numeric("mobility.speed.max_speed_road_kmh")
                offroad = self.query_numeric("mobility.speed.max_speed_offroad_kmh")
                return f"السرعة القصوى {road} كم/ساعة على الطرق الممهدة و{offroad} كم/ساعة على الطرق الوعرة"

        # Range questions
        if any(word in question_lower for word in ["مدى", "مسافة", "range"]):
            range_km = self.query_numeric("mobility.range.without_nbc_km")
            return f"المدى التشغيلي حوالي {range_km} كم"

        # Weight questions
        if any(word in question_lower for word in ["وزن", "ثقل", "weight"]):
            weight = self.query_numeric("dimensions.combat_weight_tons")
            return f"الوزن القتالي للدبابة {weight} طن"

        # Crew questions
        if any(word in question_lower for word in ["طاقم", "أفراد", "crew"]):
            crew_size = self.get("crew.size")
            roles = self.get("crew.roles_ar")
            roles_text = "، ".join(roles)
            return f"يتكون طاقم الدبابة من {crew_size} أفراد: {roles_text}"

        # Main gun questions
        if any(word in question_lower for word in ["مدفع", "عيار", "gun", "caliber"]):
            caliber = self.query_numeric("armament.main_gun.caliber_mm")
            gun_type = self.get("armament.main_gun.type_ar")
            ammo = self.query_numeric("armament.main_gun.ammo_rounds")
            return f"المدفع الرئيسي {gun_type} عيار {caliber} ملم، يحمل {ammo} طلقة"

        # Ammo questions
        if any(word in question_lower for word in ["ذخيرة", "طلقة", "ammunition"]):
            main_gun = self.query_numeric("armament.main_gun.ammo_rounds")
            commander = self.query_numeric("armament.machine_guns.commander_mg_rounds")
            mg = self.query_numeric("armament.machine_guns.total_762_rounds")
            return f"تحمل الدبابة {main_gun} طلقة للمدفع الرئيسي، {commander} طلقة لرشاش القائد، و{mg} طلقة للرشاشات عيار 7.62 ملم"

        # Engine questions
        if any(word in question_lower for word in ["محرك", "قوة", "engine", "power"]):
            power = self.query_numeric("mobility.engine.power_hp")
            engine_type = self.get("mobility.engine.type")
            model = self.get("mobility.engine.model")
            return f"محرك توربيني غازي طراز {model} بقوة {power} حصان"

        # No structured answer available
        return None


class StructuredKnowledgeService:
    """Service for managing structured knowledge bases."""

    def __init__(self):
        """Initialize structured knowledge service."""
        self.knowledge_items: Dict[str, StructuredKnowledge] = {}

        # Register M1A1 Abrams knowledge
        self.register_knowledge(M1A1AbramsKnowledge())

        logger.info(f"Structured knowledge service initialized with {len(self.knowledge_items)} items")

    def register_knowledge(self, knowledge: StructuredKnowledge) -> None:
        """Register a structured knowledge item.

        Args:
            knowledge: StructuredKnowledge instance
        """
        self.knowledge_items[knowledge.id] = knowledge
        logger.info(f"Registered structured knowledge: {knowledge.id}")

    def get_knowledge(self, knowledge_id: str) -> Optional[StructuredKnowledge]:
        """Get knowledge item by ID.

        Args:
            knowledge_id: Knowledge item ID

        Returns:
            StructuredKnowledge instance or None
        """
        return self.knowledge_items.get(knowledge_id)

    def query_all(self, question: str) -> Optional[str]:
        """Try to answer question using structured data from all knowledge items.

        Args:
            question: Question text

        Returns:
            Answer string or None
        """
        for knowledge in self.knowledge_items.values():
            if hasattr(knowledge, 'answer_question'):
                answer = knowledge.answer_question(question)
                if answer:
                    return answer

        return None

    def get_all_context_texts(self, language: str = "ar") -> str:
        """Get combined context text from all knowledge items.

        Args:
            language: Language code

        Returns:
            Combined context text
        """
        texts = []
        for knowledge in self.knowledge_items.values():
            text = knowledge.get_context_text(language)
            if text:
                texts.append(text)

        return "\n\n---\n\n".join(texts)
