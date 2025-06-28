"""Refactored Teacher Conflict Constraint using Team Teaching Service"""
from typing import List
from collections import defaultdict

from .base import HardConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import ConstraintViolation
from ..services.test_period_protector import TestPeriodProtector
from ..services.test_period_checker import TestPeriodChecker
from ..constants import GRADE5_CLASSES, WEEKDAYS, PERIODS, JIRITSU_SUBJECTS


class TeacherConflictConstraintRefactored(HardConstraint):
    """教員重複制約：同じ時間に同じ教員が複数の場所にいることを防ぐ
    
    This refactored version uses the TeamTeachingService for cleaner logic.
    """
    
    def __init__(self, learned_rule_service=None, test_period_checker: TestPeriodChecker = None):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員重複制約",
            description="同じ時間に同じ教員が複数のクラスを担当することを防ぐ"
        )
        self.test_period_protector = TestPeriodProtector()
        self.test_period_checker = test_period_checker or TestPeriodChecker()
        self.learned_rule_service = learned_rule_service
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この時間に教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        # テスト期間中は制約チェックをスキップ（教師は複数クラスの監督が可能）
        if self.test_period_protector.is_test_period(time_slot) or self.test_period_checker.is_test_period(time_slot):
            return True
        
        # 火曜5限の特別デバッグ（白石先生も追加）
        if time_slot.day == "火" and time_slot.period == 5 and assignment.teacher.name in ["白石", "井上"]:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"\n*** 教師重複制約チェック（配置前） @ 火曜5限 ***")
            logger.warning(f"  配置しようとしている: {assignment.class_ref.full_name} - {assignment.subject.name} ({assignment.teacher.name}先生)")
        
        # Get all existing assignments for this time slot
        existing_assignments = []
        for existing_assignment in schedule.get_assignments_by_time_slot(time_slot):
            if (existing_assignment.has_teacher() and 
                existing_assignment.teacher == assignment.teacher and
                existing_assignment.class_ref != assignment.class_ref):
                existing_assignments.append(
                    (existing_assignment.class_ref, existing_assignment.subject)
                )
        
        # 火曜5限の詳細デバッグ
        if time_slot.day == "火" and time_slot.period == 5 and assignment.teacher.name:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"  {assignment.teacher.name}先生の既存配置: {len(existing_assignments)}クラス")
            for cls, subj in existing_assignments:
                logger.warning(f"    - {cls.full_name}: {subj.name}")
        
        # No conflicts if no existing assignments
        if not existing_assignments:
            return True
        
        # 火曜5限の特別チェック（白石先生）
        if time_slot.day == "火" and time_slot.period == 5 and assignment.teacher.name == "白石":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"  白石先生は既に火曜5限に{len(existing_assignments)}クラスを担当しています")
            logger.warning(f"  → 配置不可（理科は同時に複数クラスで教えられない）")
            return False
        
        # Check if simultaneous teaching is allowed
        # For Grade 5 classes (1-5, 2-5, 3-5), allow simultaneous teaching
        
        # If all classes involved are Grade 5 classes, allow simultaneous teaching
        all_classes = [assignment.class_ref.full_name] + [cls.full_name for cls, _ in existing_assignments]
        if all(cls in GRADE5_CLASSES for cls in all_classes):
            return True
        
        # Check if all assignments are 自立活動 (jiritsu activities)
        all_subjects = [assignment.subject.name] + [subj.name for _, subj in existing_assignments]
        if all(subj in JIRITSU_SUBJECTS for subj in all_subjects):
            # 同じ教師が複数の自立活動を同時に担当することは可能
            return True
        
        # 学習ルールサービスがある場合はチェック
        if self.learned_rule_service:
            current_assignments = [assignment] + [a for _, a in existing_assignments]
            allowed = self.learned_rule_service.is_assignment_allowed(
                assignment.teacher.name, time_slot, current_assignments
            )
            if time_slot.day == "火" and time_slot.period == 5:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"  学習ルールチェック結果: {allowed}")
            if not allowed:
                return False
        
        # Otherwise, this is a conflict
        if time_slot.day == "火" and time_slot.period == 5:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"  最終判定: 配置不可（重複）- {assignment.teacher.name}先生")
        return False
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体検証：スケジュール全体で教員の重複をチェック"""
        violations = self._collect_all_violations(schedule, school)
        
        # 最終的な違反リストをデバッグ
        if violations:
            print(f"\n=== 教員重複制約: 最終的に{len(violations)}件の違反を返します ===")
            for v in violations[:5]:  # 最初の5件だけ表示
                print(f"  - {v.description}")
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員重複チェック完了: {len(violations)}件の違反"
        )
    
    def _collect_all_violations(self, schedule: Schedule, school: School) -> List[ConstraintViolation]:
        """全ての時間枠で違反を収集"""
        violations = []
        
        # Check each time slot
        for time_slot in self.iterate_all_time_slots():
            violations.extend(self._check_time_slot_violations(time_slot, schedule, school))
        
        return violations
    
    def _check_time_slot_violations(self, time_slot: TimeSlot, schedule: Schedule, school: School) -> List[ConstraintViolation]:
        """特定の時間枠での違反をチェック"""
        violations = []
        assignments = schedule.get_assignments_by_time_slot(time_slot)
        
        # Group assignments by teacher
        teacher_assignments = self._group_by_teacher(assignments)
        
        # 火曜5校時の教師グループ詳細
        self._debug_teacher_groups(time_slot, teacher_assignments)
        
        # Check for conflicts
        for teacher, teacher_assignments_list in teacher_assignments.items():
            if len(teacher_assignments_list) <= 1:
                continue  # No conflict possible
            
            conflict_violations = self._check_teacher_conflicts(
                teacher, teacher_assignments_list, time_slot
            )
            violations.extend(conflict_violations)
        
        return violations
    
    def _group_by_teacher(self, assignments: List['Assignment']) -> defaultdict:
        """教師ごとに割り当てをグループ化"""
        teacher_assignments = defaultdict(list)
        for assignment in assignments:
            if assignment.has_teacher():
                teacher_assignments[assignment.teacher].append(assignment)
        return teacher_assignments
    
    def _debug_teacher_groups(self, time_slot: TimeSlot, teacher_assignments: defaultdict) -> None:
        """教師グループのデバッグ情報を出力"""
        if time_slot.day == "火" and time_slot.period == 5:
            print(f"\n教師ごとのグループ:")
            for teacher, assignments_list in teacher_assignments.items():
                if len(assignments_list) > 1:
                    print(f"  {teacher}: {len(assignments_list)}クラス担当")
                    for a in assignments_list:
                        print(f"    - {a.class_ref.full_name}: {a.subject.name}")
    
    def _check_teacher_conflicts(self, teacher: 'Teacher', teacher_assignments_list: List['Assignment'], 
                                time_slot: TimeSlot) -> List[ConstraintViolation]:
        """教師の重複をチェックして違反を生成"""
        violations = []
                    
        # すべての重複をデバッグ
        self._debug_duplicate_detection(time_slot, teacher, teacher_assignments_list)
        
        # テスト期間中は教師が複数クラスの監督が可能なのでスキップ
        if self.test_period_protector.is_test_period(time_slot):
            return violations  # テスト期間中なのでスキップ
        
        # Build list of (class, subject) tuples
        class_subject_pairs = [
            (a.class_ref, a.subject) for a in teacher_assignments_list
        ]
        
        # Check each assignment against others
        for i, assignment in enumerate(teacher_assignments_list):
            # Get other assignments
            other_pairs = class_subject_pairs[:i] + class_subject_pairs[i+1:]
            
            # 許可されるケースをチェック
            if self._is_allowed_simultaneous_teaching(assignment, other_pairs, teacher, time_slot):
                continue
            
            # 違反を作成
            violation = self._create_conflict_violation(
                teacher, teacher_assignments_list, time_slot, assignment
            )
            violations.append(violation)
            break  # Only report once per teacher per time slot
        
        return violations
    
    def _debug_duplicate_detection(self, time_slot: TimeSlot, teacher: 'Teacher', 
                                  teacher_assignments_list: List['Assignment']) -> None:
        """重複検出のデバッグ情報を出力"""
        if time_slot.day == "火" and time_slot.period == 5:
            print(f"\n!!! {teacher}先生の重複検出（{len(teacher_assignments_list)}クラス） @ 火曜5校時 !!!")
            for a in teacher_assignments_list:
                print(f"    - {a.class_ref.full_name}: {a.subject.name}")
            print(f"  -> 重複チェックに進みます（2クラス以上なので）")
    
    def _is_allowed_simultaneous_teaching(self, assignment: 'Assignment', other_pairs: List[tuple], 
                                         teacher: 'Teacher', time_slot: TimeSlot) -> bool:
        """同時教えることが許可されるかチェック"""
        # Get all class names involved
        all_class_names = [assignment.class_ref.full_name] + [cls.full_name for cls, _ in other_pairs]
        
        # If all classes are Grade 5 classes, it's allowed
        if all(name in GRADE5_CLASSES for name in all_class_names):
            # 火曜5校時のデバッグ
            if time_slot.day == "火" and time_slot.period == 5:
                print(f"  -> {teacher}先生の5組チェック: すべて5組？ {all_class_names} => {all(name in GRADE5_CLASSES for name in all_class_names)}")
            return True  # This is allowed team teaching
        
        # Check if all assignments are 自立活動 (jiritsu activities)
        all_subjects = [assignment.subject.name] + [subj.name for _, subj in other_pairs]
        if all(subj in JIRITSU_SUBJECTS for subj in all_subjects):
            # 自立活動の同時実施は許可
            if time_slot.day == "火" and time_slot.period == 5:
                print(f"  -> {teacher}先生の自立活動チェック: すべて自立活動？ {all_subjects} => True")
            return True  # 自立活動の同時実施は可能
        
        # 学習ルールサービスがある場合はチェック
        if self.learned_rule_service:
            # teacher_assignments_listを再構築
            teacher_assignments_list = [assignment] + [a for _, a in other_pairs]
            allowed = self.learned_rule_service.is_assignment_allowed(
                teacher.name, time_slot, teacher_assignments_list
            )
            # 火曜5校時のデバッグ
            if time_slot.day == "火" and time_slot.period == 5:
                print(f"  -> {teacher}先生の違反作成チェック: allowed = {allowed}")
            return allowed
        
        return False
    
    def _create_conflict_violation(self, teacher: 'Teacher', teacher_assignments_list: List['Assignment'],
                                  time_slot: TimeSlot, assignment: 'Assignment') -> ConstraintViolation:
        """重複違反を作成"""
        classes_str = ", ".join(
            str(a.class_ref) for a in teacher_assignments_list
        )
        
        # 火曜5校時のデバッグ
        if time_slot.day == "火" and time_slot.period == 5:
            print(f"\n*** {teacher}先生の重複違反検出 ***")
            print(f"担当クラス数: {len(teacher_assignments_list)}")
            for idx, a in enumerate(teacher_assignments_list):
                print(f"  {idx+1}. {a.class_ref.full_name}: {a.subject.name}")
            print(f"違反メッセージ: 教員{teacher}が同時刻に複数クラスを担当: [{classes_str}]")
        
        return ConstraintViolation(
            description=f"教員{teacher}が同時刻に複数クラスを担当: [{classes_str}]",
            time_slot=time_slot,
            assignment=assignment,
            severity="ERROR"
        )