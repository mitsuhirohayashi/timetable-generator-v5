"""配置禁止制約 - 特定教科を空白セルや他教科セルに配置することを禁止"""
from typing import List, Set
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from .base import (
    Constraint, ConstraintResult, ConstraintViolation
)


class PlacementForbiddenConstraint(Constraint):
    """配置禁止制約 - 特定教科（道徳、学活等）の不適切な配置を防ぐ"""
    
    def __init__(self, forbidden_subjects: List[str]):
        """
        Args:
            forbidden_subjects: 配置禁止対象の教科リスト
        """
        from .base import ConstraintType, ConstraintPriority
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="配置禁止制約",
            description="特定教科の不適切な配置を防ぐ"
        )
        self.forbidden_subjects = set(forbidden_subjects)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """配置禁止教科が不適切に配置されていないか検証"""
        violations = []
        
        # 全ての割り当てをチェック
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in self.forbidden_subjects:
                # この教科が配置禁止教科の場合、ロックされているかチェック
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    violation = ConstraintViolation(
                        description=f"配置禁止違反: {assignment.class_ref}の{time_slot}に配置禁止教科{assignment.subject.name}が非固定で配置されています",
                        time_slot=time_slot,
                        assignment=assignment,
                        severity="ERROR"
                    )
                    violations.append(violation)
        
        return ConstraintResult(self.__class__.__name__, violations)