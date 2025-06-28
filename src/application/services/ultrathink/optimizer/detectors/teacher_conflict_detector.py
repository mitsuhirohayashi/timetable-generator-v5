"""教師重複違反検出器"""
import logging
from typing import List, Set, Tuple
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation


class TeacherConflictDetector:
    """教師重複違反を検出"""
    
    def __init__(
        self,
        test_periods: Set[Tuple[str, int]],
        grade5_refs: Set[ClassReference],
        violation_weight: float = 0.9
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
        """教師重複を検出
        
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
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定科目の教師は除外
                        if teacher_name in ["欠", "YT担当", "道担当", "学担当", 
                                          "総担当", "学総担当", "行担当", "欠課先生"]:
                            continue
                        
                        teacher_assignments[assignment.teacher].append((class_ref, assignment))
                
                # 重複をチェック
                for teacher, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        class_refs = [a[0] for a in assignments]
                        
                        # 5組のみの場合は正常
                        if all(ref in self.grade5_refs for ref in class_refs):
                            continue
                        
                        violations.append(Violation(
                            type='teacher_conflict',
                            severity=self.violation_weight,
                            time_slot=time_slot,
                            class_refs=class_refs,
                            teacher=teacher,
                            description=f"{teacher.name}先生が{len(class_refs)}クラスで重複"
                        ))
        
        return violations