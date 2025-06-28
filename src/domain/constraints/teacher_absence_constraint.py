"""教師不在制約（リファクタリング版）

ConstraintValidatorを使用して教師不在チェックロジックを統一
"""
from typing import Dict, List, Optional, Set
from .base import HardConstraint, ConstraintPriority, ConstraintResult, ConstraintViolation
from ..entities.school import School
from ..entities.schedule import Schedule
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from ..services.validators.constraint_validator import ConstraintValidator
import logging


class TeacherAbsenceConstraintRefactored(HardConstraint):
    """教師不在制約（リファクタリング版）
    
    ConstraintValidatorに委譲することで、教師不在チェックロジックを統一
    """
    
    def __init__(self, absence_loader=None):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教師不在制約",
            description="不在の教師に授業を割り当てない"
        )
        self.logger = logging.getLogger(__name__)
        self.constraint_validator = ConstraintValidator(absence_loader)
    
    def check(self, schedule: 'Schedule', school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """指定された時間帯に教師が不在でないかチェック
        
        ConstraintValidatorのロジックを使用
        """
        # 教師を取得
        teacher = assignment.teacher
        if not teacher:
            return True
        
        # ConstraintValidatorを使用して可用性をチェック
        return self.constraint_validator.check_teacher_availability(teacher, time_slot)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の教師不在制約を検証
        
        ConstraintValidatorの検証結果を使用
        """
        violations = []
        
        # ConstraintValidatorから全体の違反を取得
        all_violations = self.constraint_validator.validate_all_constraints(schedule, school)
        
        # 教師不在違反のみを抽出
        teacher_absence_violations = [v for v in all_violations if v['type'] == 'teacher_absence']
        
        # ConstraintViolationオブジェクトに変換
        for violation_info in teacher_absence_violations:
            time_slot = violation_info['time_slot']
            class_ref = violation_info['class_ref']
            
            # 該当する割り当てを取得
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if assignment:
                violation = ConstraintViolation(
                    description=violation_info['message'],
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations
        )

# Alias for backward compatibility
TeacherAbsenceConstraint = TeacherAbsenceConstraintRefactored
