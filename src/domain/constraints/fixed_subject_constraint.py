"""固定教科制約 - basics.csvで定義された教科の移動を禁止"""
from typing import List, Optional, Set
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from .base import (
    Constraint, ConstraintResult, ConstraintViolation
)
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment


class FixedSubjectConstraint(Constraint):
    """固定教科制約 - 特定の教科は初期位置から移動できない"""
    
    def __init__(self, fixed_subjects: List[str], initial_schedule: Optional[Schedule] = None):
        """
        Args:
            fixed_subjects: 固定教科のリスト（道徳、学活、YT、欠、総合、総）
            initial_schedule: 初期スケジュール（input.csv）
        """
        from .base import ConstraintType, ConstraintPriority
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="固定教科制約",
            description="basics.csvで定義された教科の移動を禁止"
        )
        self.fixed_subjects = set(fixed_subjects)
        self.initial_schedule = initial_schedule
        self._initial_positions = self._extract_initial_positions() if initial_schedule else {}
    
    def _extract_initial_positions(self) -> dict:
        """初期スケジュールから固定教科の位置を抽出"""
        positions = {}
        if not self.initial_schedule:
            return positions
            
        for time_slot, assignment in self.initial_schedule.get_all_assignments():
            if assignment.subject.name in self.fixed_subjects:
                key = (time_slot, assignment.class_ref)
                positions[key] = assignment.subject.name
        
        return positions
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """固定教科が初期位置にあるか検証"""
        violations = []
        
        # 初期スケジュールがない場合は検証をスキップ
        if not self.initial_schedule:
            return ConstraintResult(self.__class__.__name__, violations)
        
        # 現在のスケジュールで固定教科を確認
        current_fixed_positions = {}
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in self.fixed_subjects:
                key = (time_slot, assignment.class_ref)
                current_fixed_positions[key] = assignment.subject.name
        
        # 初期位置から移動していないか確認
        for key, subject_name in self._initial_positions.items():
            time_slot, class_ref = key
            current_subject = current_fixed_positions.get(key)
            
            if current_subject != subject_name:
                # 固定教科が移動または削除されている
                actual_assignment = schedule.get_assignment(time_slot, class_ref)
                actual_subject = actual_assignment.subject.name if actual_assignment else "空き"
                
                violation = ConstraintViolation(
                    description=f"固定教科違反: {class_ref}の{time_slot}は{subject_name}で固定されるべきですが、{actual_subject}になっています",
                    time_slot=time_slot,
                    assignment=actual_assignment if actual_assignment else Assignment(class_ref, Subject("空き"), None),
                    severity="ERROR"
                )
                violations.append(violation)
        
        # 固定教科が新しい位置に配置されていないか確認
        for key, subject_name in current_fixed_positions.items():
            if key not in self._initial_positions:
                time_slot, class_ref = key
                assignment = schedule.get_assignment(time_slot, class_ref)
                violation = ConstraintViolation(
                    description=f"固定教科違反: {class_ref}の{time_slot}に固定教科{subject_name}が新規配置されています",
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(self.__class__.__name__, violations)