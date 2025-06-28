"""
日内重複制約
同じクラスで同じ日に同じ教科が過度に重複しないようにする
"""

import logging
from typing import List, Optional
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..constants import WEEKDAYS, PERIODS, FIXED_SUBJECTS


class DailyDuplicateConstraint(Constraint):
    """同じ日に同じ教科が過度に重複することを防ぐ制約"""
    
    def __init__(self):
        """日内重複制約（同じ日に同じ教科の重複を禁止）"""
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,  # CRITICALに変更して最優先
            name="日内重複制約",
            description="同じ日に同じ教科の重複を禁止"
        )
        self.protected_subjects = FIXED_SUBJECTS
        self.logger = logging.getLogger(__name__)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の日内重複を検証"""
        violations = []
        
        # 全クラスの全曜日をチェック
        for class_ref in school.get_all_classes():
            for day in WEEKDAYS:
                subject_counts = self.get_daily_subject_count(schedule, class_ref, day)
                
                # 重複がある教科を検出
                for subject, count in subject_counts.items():
                    if count > 1:
                        # 違反を記録（複数回の場合は最初の重複のみ記録）
                        for period in PERIODS:
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment and assignment.subject.name == subject:
                                violation = ConstraintViolation(
                                    description=f"日内重複違反: {class_ref}の{day}曜日に{subject}が{count}回配置されています",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                                # 交流学級の重複もログに記録
                                if class_ref.is_exchange_class():
                                    self.logger.warning(f"交流学級{class_ref}で日内重複: {day}曜日に{subject}が{count}回")
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
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: チェック対象の時間枠（これから配置しようとしている時間枠）
            assignment: チェック対象の割り当て
            
        Returns:
            制約を満たす場合True、違反する場合False
        """
        # 保護された教科はチェックしない
        if assignment.subject.name in self.protected_subjects:
            return True
        
        # 同じ日の同じクラスの授業を取得（現在の時限は除外）
        same_day_count = 0
        for period in PERIODS:  # 1～6時限
            # 重要：現在チェック中の時限（これから配置する時限）はスキップ
            if period == time_slot.period:
                continue
            
            check_slot = TimeSlot(time_slot.day, period)
            existing_assignment = schedule.get_assignment(check_slot, assignment.class_ref)
            
            if (existing_assignment and 
                existing_assignment.subject.name == assignment.subject.name):
                same_day_count += 1
                # デバッグログ
                self.logger.debug(f"{assignment.class_ref}の{time_slot.day}曜日{period}時限に"
                               f"既に{assignment.subject.name}があります")
        
        # 1回でも重複があれば違反とする
        return same_day_count == 0
    
    def get_daily_subject_count(self, schedule: Schedule, class_ref, day: str) -> dict:
        """
        指定されたクラスの特定の曜日における教科別の授業数を取得
        
        Args:
            schedule: スケジュール
            class_ref: クラス参照
            day: 曜日
            
        Returns:
            教科名をキー、授業数を値とする辞書
        """
        subject_count = {}
        
        for period in PERIODS:
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if assignment and assignment.subject.name not in self.protected_subjects:
                subject_name = assignment.subject.name
                subject_count[subject_name] = subject_count.get(subject_name, 0) + 1
        
        return subject_count