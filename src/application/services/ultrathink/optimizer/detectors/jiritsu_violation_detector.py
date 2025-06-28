"""自立活動違反検出器"""
import logging
from typing import List, Dict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation


class JiritsuViolationDetector:
    """交流学級の自立活動制約違反を検出"""
    
    def __init__(self, violation_weight: float = 0.85):
        """初期化
        
        Args:
            violation_weight: 違反の重み
        """
        self.logger = logging.getLogger(__name__)
        self.violation_weight = violation_weight
        
        # 交流学級と親学級の対応関係
        self.exchange_pairs: Dict[ClassReference, ClassReference] = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
    
    def detect(self, schedule: Schedule, school: School) -> List[Violation]:
        """交流学級の自立活動制約違反を検出
        
        交流学級が自立活動の時、親学級は数学か英語でなければなりません。
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            違反のリスト
        """
        violations = []
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        
                        if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                            violations.append(Violation(
                                type='jiritsu_constraint',
                                severity=self.violation_weight,
                                time_slot=time_slot,
                                class_refs=[exchange_class, parent_class],
                                description=(
                                    f"{exchange_class}の自立活動時、"
                                    f"{parent_class}は{parent_assignment.subject.name}"
                                )
                            ))
        
        return violations