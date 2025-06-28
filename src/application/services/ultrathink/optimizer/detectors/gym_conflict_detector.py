"""体育館競合違反検出器"""
import logging
from typing import List, Set, Tuple

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School, Subject
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation


class GymConflictDetector:
    """体育館競合を検出"""
    
    def __init__(
        self,
        test_periods: Set[Tuple[str, int]],
        grade5_refs: Set[ClassReference],
        violation_weight: float = 0.7
    ):
        """初期化
        
        Args:
            test_periods: テスト期間のセット
            grade5_refs: 5組のクラス参照セット
            violation_weight: 違反の重み
        """
        self.logger = logging.getLogger(__name__)
        self.test_periods = test_periods
        self.grade5_refs = grade5_refs
        self.violation_weight = violation_weight
    
    def detect(self, schedule: Schedule, school: School) -> List[Violation]:
        """体育館競合を検出
        
        同時刻に複数のクラスが体育館を使用する場合を検出します。
        5組の合同体育は正常として扱います。
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            違反のリスト
        """
        violations = []
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間は除外
                if (day, period) in self.test_periods:
                    continue
                
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
                if len(pe_classes) > 1:
                    # 5組の合同体育は正常
                    grade5_pe = [c for c in pe_classes if c in self.grade5_refs]
                    non_grade5_pe = [c for c in pe_classes if c not in self.grade5_refs]
                    
                    # 5組以外で複数、または5組と通常学級が混在
                    if non_grade5_pe and (len(non_grade5_pe) > 1 or (grade5_pe and non_grade5_pe)):
                        violations.append(Violation(
                            type='gym_conflict',
                            severity=self.violation_weight,
                            time_slot=time_slot,
                            class_refs=pe_classes,
                            subject=Subject("保"),
                            description=f"体育館競合: {len(pe_classes)}クラス"
                        ))
        
        return violations