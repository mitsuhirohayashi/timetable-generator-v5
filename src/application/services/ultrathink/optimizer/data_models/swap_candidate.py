"""交換候補データモデル"""
from dataclasses import dataclass, field
from typing import Set

from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from .violation import Violation


@dataclass
class SwapCandidate:
    """交換候補
    
    Attributes:
        source_slot: 元のタイムスロット
        source_class: 元のクラス
        target_slot: 対象のタイムスロット
        target_class: 対象のクラス
        improvement_score: 改善スコア（正の値が改善）
        violations_fixed: 修正される違反のセット
        violations_created: 作成される違反のセット
    """
    source_slot: TimeSlot
    source_class: ClassReference
    target_slot: TimeSlot
    target_class: ClassReference
    improvement_score: float
    violations_fixed: Set[Violation] = field(default_factory=set)
    violations_created: Set[Violation] = field(default_factory=set)
    
    @property
    def net_improvement(self) -> float:
        """正味の改善度"""
        fixed_score = sum(v.severity for v in self.violations_fixed)
        created_score = sum(v.severity for v in self.violations_created)
        return fixed_score - created_score + self.improvement_score