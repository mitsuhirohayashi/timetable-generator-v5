"""日内重複制約（リファクタリング版）

ConstraintValidatorを使用して重複チェックロジックを統一
"""

from typing import List, Optional
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..constants import WEEKDAYS, PERIODS, FIXED_SUBJECTS
from ..services.validators.constraint_validator import ConstraintValidator


class DailyDuplicateConstraintRefactored(Constraint):
    """日内重複制約（リファクタリング版）
    
    ConstraintValidatorに委譲することで、重複したロジックを排除
    """
    
    def __init__(self):
        """日内重複制約（同じ日に同じ教科の重複を制限）"""
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="日内重複制約",
            description="同じ日に同じ教科の重複を制限"
        )
        self.constraint_validator = ConstraintValidator()
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の日内重複を検証"""
        violations = []
        
        # 全クラスの全曜日をチェック
        for class_ref in school.get_all_classes():
            for day in WEEKDAYS:
                # ConstraintValidatorを使用して各科目の出現回数を取得
                subject_counts = {}
                for period in PERIODS:
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in FIXED_SUBJECTS:
                        subject_name = assignment.subject.name
                        subject_counts[subject_name] = subject_counts.get(subject_name, 0) + 1
                
                # 制限を超えている科目を検出
                for subject_name, count in subject_counts.items():
                    max_allowed = self._get_max_allowed(subject_name)
                    
                    if count > max_allowed:
                        # 違反を記録（最初の超過分のみ）
                        violation_count = 0
                        for period in PERIODS:
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment and assignment.subject.name == subject_name:
                                violation_count += 1
                                if violation_count > max_allowed:
                                    violation = ConstraintViolation(
                                        description=f"日内重複違反: {class_ref}の{day}曜日に{subject_name}が{count}回配置されています（最大{max_allowed}回）",
                                        time_slot=time_slot,
                                        assignment=assignment,
                                        severity="ERROR"
                                    )
                                    violations.append(violation)
                                    break  # 最初の違反のみ記録
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"日内重複チェック完了: {len(violations)}件の違反"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """
        指定された時間枠への割り当てが日内重複制約に違反しないかチェック
        
        ConstraintValidatorのロジックを使用
        """
        # 固定科目はチェックしない
        if assignment.subject.name in FIXED_SUBJECTS:
            return True
        
        # ConstraintValidatorを使用して現在の出現回数を取得
        current_count = self.constraint_validator.get_daily_subject_count(
            schedule, assignment.class_ref, time_slot.day, assignment.subject
        )
        
        # 最大許可回数を取得
        max_allowed = self._get_max_allowed(assignment.subject.name)
        
        # 現在チェック中のスロットを含めると超過するかチェック
        return current_count < max_allowed
    
    def _get_max_allowed(self, subject_name: str) -> int:
        """科目の1日の最大許可回数を取得
        
        CLAUDE.mdに準拠：全ての教科は1日1コマまで
        """
        return 1  # 全教科1日1回まで

# Alias for backward compatibility
DailyDuplicateConstraint = DailyDuplicateConstraintRefactored
