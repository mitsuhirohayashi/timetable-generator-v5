"""非常勤教師時間制約 - 特定の教師は決められた時間帯のみ授業可能"""
from typing import List, Dict, Set, Tuple
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Teacher


class PartTimeTeacherConstraint(Constraint):
    """非常勤教師時間制約 - 青井先生（美術）は特定の時間帯のみ授業可能"""
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="非常勤教師時間制約",
            description="非常勤教師は決められた時間帯のみ授業可能"
        )
        # 青井先生が授業可能な時間帯
        self.aoi_available_slots = {
            ("水", 2), ("水", 3), ("水", 4),  # 水曜2,3,4校時
            ("木", 1), ("木", 2), ("木", 3),  # 木曜1,2,3校時
            ("金", 2), ("金", 3), ("金", 4),  # 金曜2,3,4校時
        }
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """非常勤教師が許可された時間帯のみで授業しているか検証"""
        violations = []
        
        # 各時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                for assignment in assignments:
                    # 青井先生の授業をチェック
                    if assignment.teacher and assignment.teacher.name == "青井":
                        # 5組の美術は金子み先生が担当するので除外
                        if assignment.class_ref.class_number == 5:
                            continue
                            
                        if (day, period) not in self.aoi_available_slots:
                            violation = ConstraintViolation(
                                description=f"非常勤教師時間違反: 青井先生は{day}曜{period}校時に授業できません",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"非常勤教師時間チェック完了: {len(violations)}件の違反"
        )