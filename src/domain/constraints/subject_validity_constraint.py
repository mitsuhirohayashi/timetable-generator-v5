"""教科妥当性制約"""
from typing import List

from .base import HardConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import ConstraintViolation


class SubjectValidityConstraint(HardConstraint):
    """教科妥当性制約：クラスに適さない教科の配置を防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教科妥当性制約",
            description="通常学級に特別支援教科が配置されることを防ぐ"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for time_slot, assignment in schedule.get_all_assignments():
            # 教科がクラスに適切でない場合
            if not assignment.subject.is_valid_for_class(assignment.class_ref):
                violation = ConstraintViolation(
                    description=f"クラス{assignment.class_ref}に不適切な教科{assignment.subject}が配置されています",
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教科妥当性チェック完了: {len(violations)}件の違反"
        )


class SpecialNeedsDuplicateConstraint(HardConstraint):
    """特別支援教科日内重複制約：同日内での特別支援教科重複を完全に防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.HIGH,
            name="特別支援教科日内重複制約",
            description="同日内での特別支援教科の重複を防ぐ"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for class_ref in school.get_all_classes():
            # 特別支援学級・交流学級のみチェック
            if not (class_ref.is_special_needs_class() or class_ref.is_exchange_class()):
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                subjects = schedule.get_daily_subjects(class_ref, day)
                
                # 特別支援教科の重複をチェック
                special_subjects = [s for s in subjects if s.is_special_needs_subject()]
                subject_count = {}
                
                for subject in special_subjects:
                    subject_count[subject] = subject_count.get(subject, 0) + 1
                
                # 重複している教科を特定
                for subject, count in subject_count.items():
                    if count > 1:
                        # 該当する時間枠を特定
                        for period in range(1, 7):
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment and assignment.subject == subject:
                                violation = ConstraintViolation(
                                    description=f"同日内で特別支援教科{subject}が{count}回実施されています",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"特別支援教科日内重複チェック完了: {len(violations)}件の違反"
        )