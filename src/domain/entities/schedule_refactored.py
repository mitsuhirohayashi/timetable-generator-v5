"""リファクタリング版スケジュールエンティティ - ファサードパターンを適用"""
from typing import Dict, List, Optional, Set

from .schedule_data import ScheduleData
from ..services.schedule_business_service import ScheduleBusinessService
from .grade5_unit import Grade5Unit
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment, ConstraintViolation
from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
from ...shared.mixins.validation_mixin import ValidationMixin, ValidationError


class Schedule(ValidationMixin):
    """時間割を管理するエンティティ（ファサード）
    
    既存のインターフェースを維持しながら、内部的にはScheduleDataと
    ScheduleBusinessServiceを使用してデータとロジックを分離
    """
    
    def __init__(self):
        # データ保持
        self._data = ScheduleData()
        
        # ビジネスロジック
        self._business_service = ScheduleBusinessService()
        
        # 5組ユニット
        self._grade5_unit = Grade5Unit()
        self._grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        
        # 固定科目保護の設定
        self._fixed_subject_protection_enabled = True
        
        # 制約違反（将来的には分離予定）
        self._violations: List[ConstraintViolation] = []
    
    @property
    def grade5_unit(self) -> Grade5Unit:
        """5組ユニットを取得"""
        return self._grade5_unit
    
    def assign(self, time_slot: TimeSlot, assignment: Assignment) -> None:
        """指定された時間枠にクラスの割り当てを設定"""
        # ビジネスルールチェック
        if not self._business_service.is_valid_assignment(
            self._data, time_slot, assignment.class_ref, assignment,
            self._fixed_subject_protection_enabled
        ):
            if self._data.is_locked(time_slot, assignment.class_ref):
                raise ValidationError(f"Cell is locked: {time_slot} - {assignment.class_ref}")
            else:
                raise ValidationError(f"Cannot modify fixed subject slot: {time_slot} - {assignment.class_ref}")
        
        # 5組の同期を考慮した割り当て
        if not self._business_service.assign_with_grade5_sync(
            self._data, self._grade5_unit, time_slot, assignment
        ):
            raise ValidationError(f"Failed to assign: {time_slot} - {assignment.class_ref}")
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Assignment]:
        """指定された時間枠・クラスの割り当てを取得"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_assignment(time_slot, class_ref)
        return self._data.get_assignment(time_slot, class_ref)
    
    def remove_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """指定された時間枠・クラスの割り当てを削除"""
        if self._data.is_locked(time_slot, class_ref):
            raise ValidationError(f"Cell is locked: {time_slot} - {class_ref}")
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            # 5組全体から削除
            self._grade5_unit.remove_assignment(time_slot)
            # データからも削除
            for grade5_class in self._grade5_classes:
                self._data.remove_assignment(time_slot, grade5_class)
        else:
            self._data.remove_assignment(time_slot, class_ref)
    
    def lock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルをロック（変更禁止）"""
        # 5組の場合は全5組をロック
        if class_ref in self._grade5_classes:
            self._grade5_unit.lock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._data.set_locked(time_slot, grade5_class, True)
        else:
            self._data.set_locked(time_slot, class_ref, True)
    
    def unlock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルのロックを解除"""
        # 5組の場合は全5組のロックを解除
        if class_ref in self._grade5_classes:
            self._grade5_unit.unlock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._data.set_locked(time_slot, grade5_class, False)
        else:
            self._data.set_locked(time_slot, class_ref, False)
    
    def is_locked(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルがロックされているかどうか判定"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.is_locked(time_slot)
        return self._data.is_locked(time_slot, class_ref)
    
    def disable_fixed_subject_protection(self) -> None:
        """固定科目保護を一時的に無効化"""
        self._fixed_subject_protection_enabled = False
    
    def enable_fixed_subject_protection(self) -> None:
        """固定科目保護を有効化"""
        self._fixed_subject_protection_enabled = True
    
    def get_all_assignments(self) -> List[tuple[TimeSlot, Assignment]]:
        """全ての割り当てを取得"""
        result = []
        
        # データから取得（5組以外）
        for time_slot, class_ref, assignment in self._data.get_all_assignments():
            if class_ref not in self._grade5_classes:
                result.append((time_slot, assignment))
        
        # 5組の割り当てを追加
        for time_slot, class_ref, assignment in self._grade5_unit.get_all_assignments():
            result.append((time_slot, assignment))
        
        return result
    
    def get_assignments_by_time_slot(self, time_slot: TimeSlot) -> List[Assignment]:
        """指定された時間枠の全ての割り当てを取得"""
        result = []
        
        # データから取得
        for class_ref, assignment in self._data.get_assignments_by_time_slot(time_slot).items():
            if class_ref not in self._grade5_classes:
                result.append(assignment)
        
        # 5組の割り当てを追加
        for class_ref in self._grade5_classes:
            assignment = self._grade5_unit.get_assignment(time_slot, class_ref)
            if assignment:
                result.append(assignment)
        
        return result
    
    def get_assignments_by_class(self, class_ref: ClassReference) -> List[tuple[TimeSlot, Assignment]]:
        """指定されたクラスの全ての割り当てを取得"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            result = []
            for time_slot, unit_class_ref, assignment in self._grade5_unit.get_all_assignments():
                if unit_class_ref == class_ref:
                    result.append((time_slot, assignment))
            return result
        else:
            return self._data.get_assignments_by_class(class_ref)
    
    def get_assignments_by_teacher(self, teacher: Teacher) -> List[tuple[TimeSlot, Assignment]]:
        """指定された教員の全ての割り当てを取得"""
        result = []
        for time_slot, class_ref, assignment in self._data.get_all_assignments():
            if assignment.involves_teacher(teacher):
                result.append((time_slot, assignment))
        return result
    
    def get_teacher_at_time(self, time_slot: TimeSlot, teacher: Teacher) -> List[Assignment]:
        """指定された時間枠で指定された教員が担当している割り当てを取得"""
        return self._business_service.get_teacher_assignments_at_time(
            self._data, time_slot, teacher
        )
    
    def is_teacher_available(self, time_slot: TimeSlot, teacher: Teacher) -> bool:
        """指定された時間枠で教員が空いているかどうか判定"""
        return self._business_service.is_teacher_available(
            self._data, time_slot, teacher
        )
    
    def get_empty_slots(self, class_ref: ClassReference) -> List[TimeSlot]:
        """指定されたクラスの空いている時間枠を取得"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_empty_slots()
        
        return self._business_service.get_empty_slots(self._data, class_ref)
    
    def count_subject_hours(self, class_ref: ClassReference, subject: Subject) -> int:
        """指定されたクラス・教科の週当たり時数をカウント"""
        if class_ref in self._grade5_classes:
            return self._grade5_unit.count_subject_hours(subject)
        
        return self._business_service.count_subject_hours(
            self._data, class_ref, subject
        )
    
    def get_daily_subjects(self, class_ref: ClassReference, day: str) -> List[Subject]:
        """指定されたクラス・曜日の教科一覧を取得"""
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_daily_subjects(day)
        
        return self._business_service.get_daily_subjects(
            self._data, class_ref, day
        )
    
    def has_daily_duplicate(self, class_ref: ClassReference, day: str) -> bool:
        """指定されたクラス・曜日に同じ教科が重複しているかどうか判定"""
        return self._business_service.has_daily_duplicate(
            self._data, class_ref, day
        )
    
    # 制約違反管理（将来的には別クラスに分離）
    def add_violation(self, violation: ConstraintViolation) -> None:
        """制約違反を追加"""
        self._violations.append(violation)
    
    def clear_violations(self) -> None:
        """制約違反をクリア"""
        self._violations.clear()
    
    def get_violations(self) -> List[ConstraintViolation]:
        """制約違反の一覧を取得"""
        return self._violations.copy()
    
    def has_violations(self) -> bool:
        """制約違反があるかどうか判定"""
        return len(self._violations) > 0
    
    def clone(self) -> 'Schedule':
        """スケジュールの複製を作成"""
        new_schedule = Schedule()
        
        # データの複製
        new_schedule._data = self._data.clone()
        
        # Grade5Unitの複製
        new_schedule._grade5_unit = Grade5Unit()
        for time_slot, assignment in self._grade5_unit._assignments.items():
            new_schedule._grade5_unit._assignments[time_slot] = assignment
        new_schedule._grade5_unit._locked_slots = self._grade5_unit._locked_slots.copy()
        
        # 制約違反の複製
        new_schedule._violations = self._violations.copy()
        
        # 設定の複製
        new_schedule._fixed_subject_protection_enabled = self._fixed_subject_protection_enabled
        
        return new_schedule
    
    # 互換性のためのエイリアス
    copy = clone
    
    def __str__(self) -> str:
        total_assignments = len(self._data.get_all_assignments())
        return f"Schedule(assignments={total_assignments}, violations={len(self._violations)})"