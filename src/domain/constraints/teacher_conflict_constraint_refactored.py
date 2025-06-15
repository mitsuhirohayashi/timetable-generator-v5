"""Refactored Teacher Conflict Constraint using Team Teaching Service"""
from typing import List
from collections import defaultdict

from .base import HardConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import ConstraintViolation
# from .test_period_exclusion import TestPeriodExclusionConstraint  # TODO: Enable after implementation


class TeacherConflictConstraintRefactored(HardConstraint):
    """教員重複制約：同じ時間に同じ教員が複数の場所にいることを防ぐ
    
    This refactored version uses the TeamTeachingService for cleaner logic.
    """
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員重複制約",
            description="同じ時間に同じ教員が複数のクラスを担当することを防ぐ"
        )
        # self.test_period_exclusion = TestPeriodExclusionConstraint()  # TODO: Enable after implementation
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この時間に教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        # テスト期間中は制約チェックをスキップ（TODO: テスト期間データ実装後に有効化）
        # if self.test_period_exclusion.is_test_period(time_slot, assignment.class_ref):
        #     return True
        
        # Get all existing assignments for this time slot
        existing_assignments = []
        for existing_assignment in schedule.get_assignments_by_time_slot(time_slot):
            if (existing_assignment.has_teacher() and 
                existing_assignment.teacher == assignment.teacher and
                existing_assignment.class_ref != assignment.class_ref):
                existing_assignments.append(
                    (existing_assignment.class_ref, existing_assignment.subject)
                )
        
        # No conflicts if no existing assignments
        if not existing_assignments:
            return True
        
        # Check if simultaneous teaching is allowed
        # For Grade 5 classes (1-5, 2-5, 3-5), allow simultaneous teaching
        grade5_classes = {"1年5組", "2年5組", "3年5組"}
        
        # If all classes involved are Grade 5 classes, allow simultaneous teaching
        all_classes = [assignment.class_ref.full_name] + [cls.full_name for cls, _ in existing_assignments]
        if all(cls in grade5_classes for cls in all_classes):
            return True
        
        # Otherwise, this is a conflict
        return False
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体検証：スケジュール全体で教員の重複をチェック"""
        violations = []
        
        # Check each time slot
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # Group assignments by teacher
                teacher_assignments = defaultdict(list)
                for assignment in assignments:
                    if assignment.has_teacher():
                        teacher_assignments[assignment.teacher].append(assignment)
                
                # Check for conflicts
                for teacher, teacher_assignments_list in teacher_assignments.items():
                    if len(teacher_assignments_list) <= 1:
                        continue  # No conflict possible
                    
                    # テスト期間中は全クラスをチェックして、5組以外が全てテスト期間なら除外
                    # TODO: Enable this check after test period exclusion is implemented
                    # if time_slot.day in ["月", "火", "水"] and time_slot.period <= 3:
                    #     non_grade5_in_test = all(
                    #         self.test_period_exclusion.is_test_period(time_slot, a.class_ref)
                    #         for a in teacher_assignments_list
                    #     )
                    #     if non_grade5_in_test:
                    #         continue  # テスト期間中なのでスキップ
                    
                    # Build list of (class, subject) tuples
                    class_subject_pairs = [
                        (a.class_ref, a.subject) for a in teacher_assignments_list
                    ]
                    
                    # Check each assignment against others
                    for i, assignment in enumerate(teacher_assignments_list):
                        # Get other assignments
                        other_pairs = class_subject_pairs[:i] + class_subject_pairs[i+1:]
                        
                        # Check if this assignment is allowed with others
                        # For Grade 5 classes (1-5, 2-5, 3-5), allow simultaneous teaching
                        grade5_classes = {"1年5組", "2年5組", "3年5組"}
                        
                        # Get all class names involved
                        all_class_names = [assignment.class_ref.full_name] + [cls.full_name for cls, _ in other_pairs]
                        
                        # If all classes are Grade 5 classes, it's allowed
                        if all(name in grade5_classes for name in all_class_names):
                            continue  # This is allowed team teaching
                        
                        # Otherwise, create violations for conflicts
                        allowed = False
                        if not allowed:
                            # Create violation
                            classes_str = ", ".join(
                                str(a.class_ref) for a in teacher_assignments_list
                            )
                            violation = ConstraintViolation(
                                description=f"教員{teacher}が同時刻に複数クラスを担当: [{classes_str}]",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
                            break  # Only report once per teacher per time slot
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員重複チェック完了: {len(violations)}件の違反"
        )