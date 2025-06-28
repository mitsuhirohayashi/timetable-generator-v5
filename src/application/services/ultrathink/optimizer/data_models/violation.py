"""制約違反データモデル"""
from dataclasses import dataclass
from typing import List, Optional

from .....domain.entities.school import Teacher, Subject
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference


@dataclass
class Violation:
    """制約違反
    
    Attributes:
        type: 違反タイプ（'teacher_conflict', 'daily_duplicate', 'jiritsu', etc.）
        severity: 深刻度（0.0-1.0）
        time_slot: タイムスロット
        class_refs: 関連するクラス参照リスト
        teacher: 関連する教師（オプション）
        subject: 関連する科目（オプション）
        description: 説明文
    """
    type: str
    severity: float
    time_slot: TimeSlot
    class_refs: List[ClassReference]
    teacher: Optional[Teacher] = None
    subject: Optional[Subject] = None
    description: str = ""
    
    def __hash__(self):
        return hash((self.type, self.time_slot, tuple(self.class_refs)))