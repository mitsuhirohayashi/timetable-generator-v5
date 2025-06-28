"""非常勤教師時間制約 - 特定の教師は決められた時間帯のみ授業可能"""
from typing import List, Dict, Set, Tuple, Optional
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Teacher


class PartTimeTeacherConstraint(Constraint):
    """非常勤教師時間制約 - 非常勤教師は決められた時間帯のみ授業可能
    
    QA.txtから読み込んだルールに基づいて制約をチェックします。
    """
    
    def __init__(self, part_time_schedules: Optional[Dict[str, List[Tuple[str, int]]]] = None):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="非常勤教師時間制約",
            description="非常勤教師は決められた時間帯のみ授業可能"
        )
        # 非常勤教師の勤務可能時間を外部から注入（デフォルトは空）
        self.part_time_schedules = part_time_schedules or {}
        
        # 各教師の利用可能スロットをセットに変換
        self.teacher_available_slots = {}
        for teacher, slots in self.part_time_schedules.items():
            self.teacher_available_slots[teacher] = set(slots)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """非常勤教師が許可された時間帯のみで授業しているか検証"""
        violations = []
        
        # 各時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                for assignment in assignments:
                    if not assignment.teacher:
                        continue
                    
                    # 非常勤教師のチェック
                    teacher_name = assignment.teacher.name
                    if teacher_name in self.teacher_available_slots:
                        # 5組の美術は特別扱い（金子み先生が担当）の場合は除外
                        if teacher_name == "青井" and assignment.class_ref.class_number == 5:
                            continue
                        
                        # 利用可能な時間帯かチェック
                        if (day, period) not in self.teacher_available_slots[teacher_name]:
                            violation = ConstraintViolation(
                                description=f"非常勤教師時間違反: {teacher_name}先生は{day}曜{period}校時に授業できません",
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