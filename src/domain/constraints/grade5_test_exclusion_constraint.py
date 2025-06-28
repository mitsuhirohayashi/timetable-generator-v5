"""
Grade 5 Test Exclusion Constraint

This constraint ensures that Grade 5 classes (1-5, 2-5, 3-5) do not have 
the same subject that regular classes in their grade are taking as a test 
during test periods.

For example, if Grade 1 regular classes (1-1, 1-2, 1-3) are taking a math test,
Grade 1-5 should NOT have math during that period.
"""

from typing import List, Optional, Set
from .base import Constraint, ConstraintViolation, ConstraintPriority, ConstraintType, ConstraintResult
from ..entities.schedule import Schedule
from ..entities.school import School
import logging

logger = logging.getLogger(__name__)


class Grade5TestExclusionConstraint(Constraint):
    """
    Prevents Grade 5 classes from having the same subject that regular classes
    are taking as a test during test periods.
    """
    
    def __init__(self):
        """Initialize the Grade 5 test exclusion constraint."""
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="Grade5TestExclusion",
            description="5組はテスト期間中、通常クラスがテストを受けている科目を受けられない"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """
        Validate if any Grade 5 class has the same subject as a test during test periods.
        
        Args:
            schedule: The schedule to check
            school: School information
            
        Returns:
            ConstraintResult with any violations found
        """
        violations = []
        
        # Get test periods from schedule
        test_periods = getattr(schedule, 'test_periods', {})
        if not test_periods:
            return violations
        
        # Grade 5 classes
        grade5_classes = {"1-5", "2-5", "3-5"}
        
        # Check each test period
        for day, periods in test_periods.items():
            for period in periods:
                # Get test subjects for regular classes in each grade
                test_subjects_by_grade = self._get_test_subjects_by_grade(
                    schedule, day, period, grade5_classes
                )
                
                # Check Grade 5 classes
                for grade5_class in grade5_classes:
                    grade_num = grade5_class[0]  # Extract grade number (1, 2, or 3)
                    
                    # Get subject for this Grade 5 class
                    from ..value_objects.time_slot import TimeSlot, ClassReference
                    time_slot = TimeSlot(day, period)
                    # Parse class name to get ClassReference
                    grade_num_str, class_num_str = grade5_class.split("-")
                    class_ref = ClassReference(int(grade_num_str), int(class_num_str))
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment or assignment.subject.name == "欠":
                        continue
                    subject = assignment.subject.name
                    
                    # Check if this subject is being tested in the same grade
                    if grade_num in test_subjects_by_grade:
                        test_subjects = test_subjects_by_grade[grade_num]
                        if subject in test_subjects:
                            violations.append(ConstraintViolation(
                                description=(
                                    f"{grade5_class}が{day}曜{period}限に{subject}を受けていますが、"
                                    f"同学年の通常クラスが{subject}のテストを受けています"
                                ),
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=f"Found {len(violations)} Grade 5 test exclusion violations" if violations else None
        )
    
    def _get_test_subjects_by_grade(
        self, 
        schedule: Schedule, 
        day: str, 
        period: int, 
        grade5_classes: Set[str]
    ) -> dict:
        """
        Get test subjects for each grade's regular classes.
        
        Args:
            schedule: The schedule
            day: Day of the week
            period: Period number
            grade5_classes: Set of Grade 5 classes to exclude
            
        Returns:
            Dictionary mapping grade number to set of test subjects
        """
        test_subjects_by_grade = {}
        
        # Check all classes
        from ..value_objects.time_slot import TimeSlot, ClassReference
        time_slot = TimeSlot(day, period)
        
        # Get all assignments at this time slot
        assignments = schedule.get_assignments_by_time_slot(time_slot)
        
        for assignment in assignments:
            class_ref = assignment.class_ref
            class_name = f"{class_ref.grade}-{class_ref.class_number}"
            
            # Skip Grade 5 classes
            if class_name in grade5_classes:
                continue
            
            # Skip exchange classes (6組, 7組)
            if class_ref.class_number in [6, 7]:
                continue
            
            # Get grade number
            grade_num = str(class_ref.grade)
            if grade_num in ["1", "2", "3"]:
                subject = assignment.subject.name
                
                # During test periods, all subjects are considered test subjects
                # (even if they don't have "テスト" in the name)
                if subject and subject != "欠":
                    if grade_num not in test_subjects_by_grade:
                        test_subjects_by_grade[grade_num] = set()
                    
                    # Extract the actual subject from test notation
                    actual_subject = self._extract_subject_from_test(subject)
                    if actual_subject:
                        test_subjects_by_grade[grade_num].add(actual_subject)
        
        return test_subjects_by_grade
    
    def _is_test_subject(self, subject: str) -> bool:
        """
        Check if a subject string indicates a test.
        
        Args:
            subject: Subject string
            
        Returns:
            True if it's a test subject
        """
        if not subject:
            return False
        
        # Common test indicators
        test_indicators = ["テスト", "test", "TEST", "試験"]
        
        # Check if subject contains test indicators
        for indicator in test_indicators:
            if indicator in subject:
                return True
        
        # Check for specific test subjects (e.g., "数" for math test)
        # Note: During test periods, regular subjects might just show as "数", "英", etc.
        # We need to check if we're in a test period
        return False
    
    def _extract_subject_from_test(self, test_subject: str) -> Optional[str]:
        """
        Extract the actual subject from a test notation.
        
        Args:
            test_subject: Test subject string (e.g., "数学テスト", "数")
            
        Returns:
            The actual subject (e.g., "数", "英")
        """
        # If it's already a simple subject code, return it
        if test_subject in ["国", "数", "英", "理", "社", "音", "美", "体", "技", "家"]:
            return test_subject
        
        # Remove test-related suffixes
        for suffix in ["テスト", "test", "TEST", "試験"]:
            if test_subject.endswith(suffix):
                return test_subject.replace(suffix, "").strip()
        
        # For compound subjects like "技家", keep as is
        return test_subject
    
    def check(self, schedule: Schedule, school: School, time_slot: 'TimeSlot', 
              assignment: 'Assignment') -> bool:
        """
        Check if a placement would violate the Grade 5 test exclusion constraint.
        
        Args:
            schedule: Current schedule
            school: School information
            time_slot: Time slot for the assignment
            assignment: Assignment to check
            
        Returns:
            True if the placement is allowed, False otherwise
        """
        # Only check Grade 5 classes
        class_ref = assignment.class_ref
        class_name = f"{class_ref.grade}-{class_ref.class_number}"
        if class_name not in {"1-5", "2-5", "3-5"}:
            return True
        
        # Get test periods
        test_periods = getattr(schedule, 'test_periods', {})
        if not test_periods:
            return True
        
        # Check if current slot is in a test period
        if time_slot.day not in test_periods or time_slot.period not in test_periods[time_slot.day]:
            return True
        
        # Get grade number
        grade_num = str(class_ref.grade)
        
        # Check what subjects regular classes are testing
        test_subjects_by_grade = self._get_test_subjects_by_grade(
            schedule, time_slot.day, time_slot.period, {"1-5", "2-5", "3-5"}
        )
        
        # If this grade has test subjects, check if our subject matches
        if grade_num in test_subjects_by_grade:
            test_subjects = test_subjects_by_grade[grade_num]
            if assignment.subject.name in test_subjects:
                return False
        
        return True
    
