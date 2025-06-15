"""スケジュールエンティティ"""
from typing import Dict, List, Optional, Set
from collections import defaultdict

from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment, ConstraintViolation
from .grade5_unit import Grade5Unit


class Schedule:
    """時間割を管理するエンティティ"""
    
    def __init__(self):
        self._assignments: Dict[TimeSlot, Dict[ClassReference, Assignment]] = defaultdict(dict)
        self._locked_cells: Set[tuple[TimeSlot, ClassReference]] = set()
        self._violations: List[ConstraintViolation] = []
        # 5組ユニット
        self._grade5_unit = Grade5Unit()
        self._grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        # 固定科目保護ポリシー
        from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
        self._fixed_subject_policy = FixedSubjectProtectionPolicy()
        self._fixed_subject_protection_enabled = True
    
    @property
    def grade5_unit(self) -> Grade5Unit:
        """5組ユニットを取得"""
        return self._grade5_unit
    
    def assign(self, time_slot: TimeSlot, assignment: Assignment) -> None:
        """指定された時間枠にクラスの割り当てを設定"""
        if self.is_locked(time_slot, assignment.class_ref):
            raise ValueError(f"Cell is locked: {time_slot} - {assignment.class_ref}")
        
        # 固定科目保護チェック（有効な場合のみ）
        if self._fixed_subject_protection_enabled:
            if not self._fixed_subject_policy.can_modify_slot(self, time_slot, assignment.class_ref, assignment):
                raise ValueError(f"Cannot modify fixed subject slot: {time_slot} - {assignment.class_ref}")
        
        # 5組の場合は特別処理
        if assignment.class_ref in self._grade5_classes:
            # 5組全体に同じ教科・教員を割り当て
            # ただし、ロックされているセルはスキップ
            can_assign_to_unit = True
            for grade5_class in self._grade5_classes:
                if self.is_locked(time_slot, grade5_class):
                    can_assign_to_unit = False
                    break
            
            if can_assign_to_unit:
                # 全ての5組セルがロックされていない場合のみユニットに割り当て
                self._grade5_unit.assign(time_slot, assignment.subject, assignment.teacher)
                # 通常の割り当ても行う（互換性のため）
                for grade5_class in self._grade5_classes:
                    self._assignments[time_slot][grade5_class] = Assignment(
                        grade5_class, assignment.subject, assignment.teacher
                    )
            else:
                # 一部がロックされている場合は、個別に割り当て（同期は崩れる可能性がある）
                if not self.is_locked(time_slot, assignment.class_ref):
                    self._assignments[time_slot][assignment.class_ref] = assignment
        else:
            self._assignments[time_slot][assignment.class_ref] = assignment
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Assignment]:
        """指定された時間枠・クラスの割り当てを取得"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_assignment(time_slot, class_ref)
        return self._assignments[time_slot].get(class_ref)
    
    def remove_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """指定された時間枠・クラスの割り当てを削除"""
        if self.is_locked(time_slot, class_ref):
            raise ValueError(f"Cell is locked: {time_slot} - {class_ref}")
        
        # 固定科目保護チェック（有効な場合のみ）
        if self._fixed_subject_protection_enabled:
            if not self._fixed_subject_policy.can_modify_slot(self, time_slot, class_ref, None):
                raise ValueError(f"Cannot remove from fixed subject slot: {time_slot} - {class_ref}")
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            # 5組全体から削除
            self._grade5_unit.remove_assignment(time_slot)
            # 通常の割り当ても削除（互換性のため）
            for grade5_class in self._grade5_classes:
                if time_slot in self._assignments and grade5_class in self._assignments[time_slot]:
                    del self._assignments[time_slot][grade5_class]
        else:
            if time_slot in self._assignments and class_ref in self._assignments[time_slot]:
                del self._assignments[time_slot][class_ref]
    
    def lock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルをロック（変更禁止）"""
        # 5組の場合は全5組をロック
        if class_ref in self._grade5_classes:
            self._grade5_unit.lock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._locked_cells.add((time_slot, grade5_class))
        else:
            self._locked_cells.add((time_slot, class_ref))
    
    def unlock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルのロックを解除"""
        # 5組の場合は全5組のロックを解除
        if class_ref in self._grade5_classes:
            self._grade5_unit.unlock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._locked_cells.discard((time_slot, grade5_class))
        else:
            self._locked_cells.discard((time_slot, class_ref))
    
    def is_locked(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルがロックされているかどうか判定"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.is_locked(time_slot)
        return (time_slot, class_ref) in self._locked_cells
    
    def disable_fixed_subject_protection(self) -> None:
        """固定科目保護を一時的に無効化"""
        self._fixed_subject_protection_enabled = False
    
    def enable_fixed_subject_protection(self) -> None:
        """固定科目保護を有効化"""
        self._fixed_subject_protection_enabled = True
    
    def get_all_assignments(self) -> List[tuple[TimeSlot, Assignment]]:
        """全ての割り当てを取得"""
        result = []
        # 5組以外の通常の割り当て
        for time_slot, class_assignments in self._assignments.items():
            for class_ref, assignment in class_assignments.items():
                # 5組は後で追加するのでスキップ
                if class_ref not in self._grade5_classes:
                    result.append((time_slot, assignment))
        
        # 5組の割り当てを追加
        for time_slot, class_ref, assignment in self._grade5_unit.get_all_assignments():
            result.append((time_slot, assignment))
        
        return result
    
    def get_assignments_by_time_slot(self, time_slot: TimeSlot) -> List[Assignment]:
        """指定された時間枠の全ての割り当てを取得"""
        result = []
        # 5組以外の通常の割り当て
        for class_ref, assignment in self._assignments[time_slot].items():
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
        result = []
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            for time_slot, unit_class_ref, assignment in self._grade5_unit.get_all_assignments():
                if unit_class_ref == class_ref:
                    result.append((time_slot, assignment))
        else:
            # 通常の処理
            for time_slot, class_assignments in self._assignments.items():
                if class_ref in class_assignments:
                    result.append((time_slot, class_assignments[class_ref]))
        
        return result
    
    def get_assignments_by_teacher(self, teacher: Teacher) -> List[tuple[TimeSlot, Assignment]]:
        """指定された教員の全ての割り当てを取得"""
        result = []
        for time_slot, class_assignments in self._assignments.items():
            for assignment in class_assignments.values():
                if assignment.involves_teacher(teacher):
                    result.append((time_slot, assignment))
        return result
    
    def get_teacher_at_time(self, time_slot: TimeSlot, teacher: Teacher) -> List[Assignment]:
        """指定された時間枠で指定された教員が担当している割り当てを取得"""
        assignments = self.get_assignments_by_time_slot(time_slot)
        result = [a for a in assignments if a.involves_teacher(teacher)]
        
        # 5組の場合、1つの教員が3クラスを同時に担当していることを正しく反映
        grade5_assignments = [a for a in result if a.class_ref in self._grade5_classes]
        if len(grade5_assignments) > 1:
            # 5組の授業は1つとしてカウント（実際には3クラス同時指導）
            # 最初の1つだけを残す
            result = [a for a in result if a.class_ref not in self._grade5_classes]
            if grade5_assignments:
                result.append(grade5_assignments[0])
        
        return result
    
    def is_teacher_available(self, time_slot: TimeSlot, teacher: Teacher) -> bool:
        """指定された時間枠で教員が空いているかどうか判定"""
        assignments = self.get_teacher_at_time(time_slot, teacher)
        # 5組の教員は3クラス同時に教えるため、特別な判定は不要
        return len(assignments) == 0
    
    def get_empty_slots(self, class_ref: ClassReference) -> List[TimeSlot]:
        """指定されたクラスの空いている時間枠を取得"""
        all_time_slots = [
            TimeSlot(day, period) 
            for day in ["月", "火", "水", "木", "金"] 
            for period in range(1, 7)
        ]
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_empty_slots()
        
        assigned_slots = {ts for ts, _ in self.get_assignments_by_class(class_ref)}
        # ロックされているセルも除外
        locked_slots = {ts for ts in all_time_slots if self.is_locked(ts, class_ref)}
        return [ts for ts in all_time_slots if ts not in assigned_slots and ts not in locked_slots]
    
    def count_subject_hours(self, class_ref: ClassReference, subject: Subject) -> int:
        """指定されたクラス・教科の週当たり時数をカウント"""
        assignments = self.get_assignments_by_class(class_ref)
        return sum(1 for _, assignment in assignments if assignment.subject == subject)
    
    def get_daily_subjects(self, class_ref: ClassReference, day: str) -> List[Subject]:
        """指定されたクラス・曜日の教科一覧を取得"""
        subjects = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = self.get_assignment(time_slot, class_ref)
            if assignment:
                subjects.append(assignment.subject)
        return subjects
    
    def has_daily_duplicate(self, class_ref: ClassReference, day: str) -> bool:
        """指定されたクラス・曜日に同じ教科が重複しているかどうか判定"""
        subjects = self.get_daily_subjects(class_ref, day)
        return len(subjects) != len(set(subjects))
    
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
        new_schedule._assignments = {
            ts: dict(assignments) for ts, assignments in self._assignments.items()
        }
        new_schedule._locked_cells = self._locked_cells.copy()
        new_schedule._violations = self._violations.copy()
        # Grade5Unitも複製
        new_schedule._grade5_unit = Grade5Unit()
        for time_slot, assignment in self._grade5_unit._assignments.items():
            new_schedule._grade5_unit._assignments[time_slot] = assignment
        new_schedule._grade5_unit._locked_slots = self._grade5_unit._locked_slots.copy()
        return new_schedule
    
    def __str__(self) -> str:
        total_assignments = sum(len(assignments) for assignments in self._assignments.values())
        return f"Schedule(assignments={total_assignments}, violations={len(self._violations)})"