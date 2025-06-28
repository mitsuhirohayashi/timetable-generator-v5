"""スケジュールビジネスサービス - スケジュールに関するビジネスロジック"""
from typing import List, Optional, Set
import logging
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule_data import ScheduleData
from ...entities.grade5_unit import Grade5Unit
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ...policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy


class ScheduleBusinessService(LoggingMixin):
    """スケジュールに関するビジネスロジックを提供するサービス"""
    
    def __init__(self):
        super().__init__()
        self._grade5_classes = {
            ClassReference(1, 5), 
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        self._fixed_subject_policy = FixedSubjectProtectionPolicy()
    
    def is_valid_assignment(self, schedule_data: ScheduleData, time_slot: TimeSlot,
                          class_ref: ClassReference, assignment: Assignment,
                          fixed_subject_protection_enabled: bool = True) -> bool:
        """割り当てが妥当かどうかを判定"""
        # ロックチェック
        if schedule_data.is_locked(time_slot, class_ref):
            return False
        
        # 固定科目保護チェック
        if fixed_subject_protection_enabled:
            # 既存のScheduleインターフェースに合わせるためのアダプター処理が必要
            # ここでは簡略化
            existing = schedule_data.get_assignment(time_slot, class_ref)
            if existing and existing.subject.name in self._fixed_subject_policy.get_fixed_subjects():
                return False
        
        return True
    
    def assign_with_grade5_sync(self, schedule_data: ScheduleData, grade5_unit: Grade5Unit,
                               time_slot: TimeSlot, assignment: Assignment) -> bool:
        """5組の同期を考慮した割り当て"""
        # 5組の場合は特別処理
        if assignment.class_ref in self._grade5_classes:
            # 全ての5組がロックされていないかチェック
            can_assign_to_unit = True
            for grade5_class in self._grade5_classes:
                if schedule_data.is_locked(time_slot, grade5_class):
                    can_assign_to_unit = False
                    break
            
            if can_assign_to_unit:
                # Grade5Unitに割り当て
                try:
                    grade5_unit.assign(time_slot, assignment.subject, assignment.teacher)
                    # 各クラスのデータも更新
                    for grade5_class in self._grade5_classes:
                        schedule_data.set_assignment(
                            time_slot, grade5_class,
                            Assignment(grade5_class, assignment.subject, assignment.teacher)
                        )
                    return True
                except ValueError:
                    return False
            else:
                # 個別に割り当て（同期は崩れる）
                if not schedule_data.is_locked(time_slot, assignment.class_ref):
                    schedule_data.set_assignment(time_slot, assignment.class_ref, assignment)
                    return True
                return False
        else:
            # 通常の割り当て
            schedule_data.set_assignment(time_slot, assignment.class_ref, assignment)
            return True
    
    def get_teacher_assignments_at_time(self, schedule_data: ScheduleData, 
                                       time_slot: TimeSlot, teacher: Teacher) -> List[Assignment]:
        """指定時間の教師の割り当てを取得（5組の特別処理含む）"""
        assignments = []
        for class_ref, assignment in schedule_data.get_assignments_by_time_slot(time_slot).items():
            if assignment.teacher and assignment.teacher.name == teacher.name:
                assignments.append(assignment)
        
        # 5組の場合、重複を除去（3クラス同時指導を1つとしてカウント）
        grade5_assignments = [a for a in assignments if a.class_ref in self._grade5_classes]
        if len(grade5_assignments) > 1:
            # 5組以外の割り当て + 5組の代表1つ
            non_grade5 = [a for a in assignments if a.class_ref not in self._grade5_classes]
            return non_grade5 + [grade5_assignments[0]]
        
        return assignments
    
    def is_teacher_available(self, schedule_data: ScheduleData,
                           time_slot: TimeSlot, teacher: Teacher) -> bool:
        """教師が利用可能かどうかを判定"""
        assignments = self.get_teacher_assignments_at_time(schedule_data, time_slot, teacher)
        return len(assignments) == 0
    
    def get_daily_subjects(self, schedule_data: ScheduleData,
                          class_ref: ClassReference, day: str) -> List[Subject]:
        """指定クラス・曜日の教科リストを取得"""
        subjects = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule_data.get_assignment(time_slot, class_ref)
            if assignment:
                subjects.append(assignment.subject)
        return subjects
    
    def has_daily_duplicate(self, schedule_data: ScheduleData,
                           class_ref: ClassReference, day: str,
                           excluded_subjects: Set[str] = None) -> bool:
        """日内重複があるかどうかを判定"""
        if excluded_subjects is None:
            excluded_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        
        subjects = self.get_daily_subjects(schedule_data, class_ref, day)
        # 保護教科を除外
        countable_subjects = [s for s in subjects if s.name not in excluded_subjects]
        
        # 重複チェック
        return len(countable_subjects) != len(set(countable_subjects))
    
    def count_subject_hours(self, schedule_data: ScheduleData,
                           class_ref: ClassReference, subject: Subject) -> int:
        """指定クラス・教科の週間時数をカウント"""
        count = 0
        for time_slot, assignment in schedule_data.get_assignments_by_class(class_ref):
            if assignment.subject == subject:
                count += 1
        return count
    
    def get_empty_slots(self, schedule_data: ScheduleData,
                       class_ref: ClassReference) -> List[TimeSlot]:
        """空きスロットを取得"""
        all_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                all_slots.append(TimeSlot(day, period))
        
        # 割り当て済みとロック済みを除外
        empty_slots = []
        for time_slot in all_slots:
            if (not schedule_data.get_assignment(time_slot, class_ref) and
                not schedule_data.is_locked(time_slot, class_ref)):
                empty_slots.append(time_slot)
        
        return empty_slots