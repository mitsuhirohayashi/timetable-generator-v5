"""月曜6校時固定制約 - 全クラスの月曜6校時を欠課として固定"""
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from .base import (
    Constraint, ConstraintResult, ConstraintViolation
)
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.domain.value_objects.time_slot import Subject


class MondaySixthPeriodConstraint(Constraint):
    """月曜6校時固定制約 - 全クラスの月曜6校時は欠課で固定"""
    
    def __init__(self):
        from .base import ConstraintType, ConstraintPriority
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="月曜6校時固定制約",
            description="全クラスの月曜6校時を欠課で固定"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """配置前チェック：月曜6校時は欠課のみ許可（3年生を除く）"""
        # 月曜6校時の場合
        if time_slot.day == "月" and time_slot.period == 6:
            # 3年生は制約を適用しない
            if assignment.class_ref.grade == 3:
                return True
            # 1,2年生は欠課のみ許可
            return assignment.subject.name == '欠'
        # それ以外の時間は制約なし
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """月曜6校時が欠課になっているか検証"""
        violations = []
        
        # 月曜6校時のTimeSlot
        monday_sixth = TimeSlot("月", 6)  # 月曜6校時
        
        # 全クラスをチェック
        for class_ref in school.get_all_classes():
            # 3年生は制約を適用しない
            if class_ref.grade == 3:
                continue
                
            assignment = schedule.get_assignment(monday_sixth, class_ref)
            
            # 欠課でない場合は違反
            if not assignment or assignment.subject.name != '欠':
                actual_subject = assignment.subject.name if assignment else "空き"
                violation = ConstraintViolation(
                    description=f"月曜6校時固定違反: {class_ref}の月曜6校時は欠課であるべきですが、{actual_subject}になっています",
                    time_slot=monday_sixth,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(self.__class__.__name__, violations)