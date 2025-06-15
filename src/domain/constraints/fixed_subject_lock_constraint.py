"""固定教科ロック制約 - input.csvから読み込んだ固定教科のロックが維持されているか検証"""
from typing import List
from .base import Constraint, ConstraintType, ConstraintPriority, ConstraintViolation, ConstraintResult
from ..value_objects.subject_validator import SubjectValidator
import logging


class FixedSubjectLockConstraint(Constraint):
    """固定教科のロックが維持されているか検証する制約
    
    欠、YT、学、道、総、行などの固定教科が
    input.csvから読み込んだ位置から移動していないかチェック
    """
    
    def __init__(self, initial_schedule=None):
        """初期化
        
        Args:
            initial_schedule: input.csvから読み込んだ初期スケジュール
        """
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="固定教科ロック制約",
            description="固定教科（欠、YT、学など）はinput.csvの位置から移動禁止"
        )
        self.initial_schedule = initial_schedule
        self.logger = logging.getLogger(__name__)
        self.validator = SubjectValidator()
    
    def validate(self, schedule, school) -> ConstraintResult:
        """制約の検証"""
        violations = []
        
        # 初期スケジュールがない場合はスキップ
        if not self.initial_schedule:
            return ConstraintResult(self, violations)
        
        # 固定教科のリスト
        validator = SubjectValidator()
        fixed_subjects = list(validator.fixed_subjects)
        
        # 全クラスの全時間枠をチェック
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    from ..value_objects.time_slot import TimeSlot
                    time_slot = TimeSlot(day, period)
                    
                    # 初期スケジュールの割り当て
                    initial_assignment = self.initial_schedule.get_assignment(time_slot, class_ref)
                    
                    # 初期スケジュールに固定教科があった場合
                    if initial_assignment and initial_assignment.subject.name in fixed_subjects:
                        # 現在のスケジュールの割り当て
                        current_assignment = schedule.get_assignment(time_slot, class_ref)
                        
                        # 固定教科が削除または変更されている場合
                        if not current_assignment or current_assignment.subject != initial_assignment.subject:
                            violations.append(ConstraintViolation(
                                description=f"{time_slot}: {class_ref}の固定教科{initial_assignment.subject}が"
                                          f"{'削除' if not current_assignment else f'{current_assignment.subject}に変更'}されました",
                                time_slot=time_slot,
                                assignment=current_assignment if current_assignment else initial_assignment,
                                severity="ERROR"
                            ))
                    
                    # 固定教科が新たに追加されている場合もチェック
                    current_assignment = schedule.get_assignment(time_slot, class_ref)
                    if current_assignment and current_assignment.subject.name in fixed_subjects:
                        # 初期スケジュールになかった固定教科が追加されている
                        if not initial_assignment or initial_assignment.subject.name not in fixed_subjects:
                            violations.append(ConstraintViolation(
                                description=f"{time_slot}: {class_ref}に固定教科{current_assignment.subject}が"
                                          f"新規追加されました（初期: {initial_assignment.subject if initial_assignment else '空き'}）",
                                time_slot=time_slot,
                                assignment=current_assignment,
                                severity="ERROR"
                            ))
        
        return ConstraintResult(self, violations)
    
    def check(self, schedule, school, time_slot, assignment) -> bool:
        """配置前の事前チェック
        
        Returns:
            bool: 配置が許可される場合True
        """
        # 初期スケジュールがない場合は許可
        if not self.initial_schedule:
            return True
        
        # 初期スケジュールの割り当てを確認
        initial_assignment = self.initial_schedule.get_assignment(time_slot, assignment.class_ref)
        
        # 初期スケジュールに固定教科がある場合
        if initial_assignment and initial_assignment.subject.name in self.validator.fixed_subjects:
            # 同じ教科なら許可
            if assignment.subject.name == initial_assignment.subject.name:
                return True
            # 違う教科なら拒否
            else:
                self.logger.warning(
                    f"固定教科ロック違反: {time_slot} {assignment.class_ref} - "
                    f"初期: {initial_assignment.subject.name}, 新規: {assignment.subject.name}"
                )
                return False
        
        # 固定教科を新規配置しようとしている場合
        if assignment.subject.name in self.validator.fixed_subjects:
            # 初期スケジュールになかった固定教科は配置不可
            if not initial_assignment or initial_assignment.subject.name != assignment.subject.name:
                self.logger.warning(
                    f"固定教科の新規配置を拒否: {time_slot} {assignment.class_ref} - "
                    f"{assignment.subject.name}"
                )
                return False
        
        return True