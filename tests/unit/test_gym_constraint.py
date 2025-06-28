#!/usr/bin/env python3
"""Test gym usage constraint with the new configuration"""

import sys
sys.path.append('.')

from src.domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment, ClassReference, Subject, Teacher
from src.infrastructure.parsers.base_timetable_parser import BaseTimetableParser
from src.infrastructure.parsers.teacher_parser import TeacherParser
from src.infrastructure.repositories.csv_repository import CSVRepository

# Load school data
csv_repo = CSVRepository()
base_timetable_parser = BaseTimetableParser()
teacher_parser = TeacherParser()

base_timetable_data = base_timetable_parser.parse('data/config/base_timetable.csv')
teacher_data = teacher_parser.parse('data/config/default_teacher_mapping.csv')

# Create school
school = School()
# Add basic classes
for grade in range(1, 4):
    for class_num in range(1, 4):
        school.add_class(ClassReference(grade, class_num))
    # Add support classes
    school.add_class(ClassReference(grade, 5))
    school.add_class(ClassReference(grade, 6))
    school.add_class(ClassReference(grade, 7))

# Create schedule
schedule = Schedule()

# Create test assignments
constraint = GymUsageConstraintRefactored()

# Test cases
test_cases = [
    {
        'name': 'Grade 5 joint PE',
        'assignments': [
            Assignment(ClassReference(1, 5), Subject("保"), Teacher("体育教師1")),
            Assignment(ClassReference(2, 5), Subject("保"), Teacher("体育教師1")),
            Assignment(ClassReference(3, 5), Subject("保"), Teacher("体育教師1"))
        ],
        'time_slot': TimeSlot("月", 1),
        'expected': True
    },
    {
        'name': 'Exchange pair 1-6 and 1-1',
        'assignments': [
            Assignment(ClassReference(1, 6), Subject("保"), Teacher("体育教師2")),
            Assignment(ClassReference(1, 1), Subject("保"), Teacher("体育教師2"))
        ],
        'time_slot': TimeSlot("月", 2),
        'expected': True
    },
    {
        'name': 'Non-paired classes',
        'assignments': [
            Assignment(ClassReference(1, 1), Subject("保"), Teacher("体育教師3")),
            Assignment(ClassReference(2, 2), Subject("保"), Teacher("体育教師4"))
        ],
        'time_slot': TimeSlot("月", 3),
        'expected': False
    }
]

print("Testing gym usage constraint with new configuration:")
print("=" * 80)

for test in test_cases:
    print(f"\nTest: {test['name']}")
    print(f"Time: {test['time_slot']}")
    
    # Clear schedule for this test
    schedule = Schedule()
    
    # Try to assign each class
    all_assigned = True
    for i, assignment in enumerate(test['assignments']):
        if i == 0:
            # First assignment should always succeed
            can_assign = constraint.check(schedule, school, test['time_slot'], assignment)
            if can_assign:
                schedule.assign(test['time_slot'], assignment)
                print(f"  ✓ Assigned: {assignment.class_ref} - {assignment.subject}")
            else:
                print(f"  ✗ Failed to assign: {assignment.class_ref} - {assignment.subject}")
                all_assigned = False
        else:
            # Check if we can add this assignment
            can_assign = constraint.check(schedule, school, test['time_slot'], assignment)
            if can_assign:
                schedule.assign(test['time_slot'], assignment)
                print(f"  ✓ Assigned: {assignment.class_ref} - {assignment.subject}")
            else:
                print(f"  ✗ Cannot assign: {assignment.class_ref} - {assignment.subject}")
                all_assigned = False
    
    # Check result
    if all_assigned == test['expected']:
        print(f"  Result: PASS (expected={test['expected']}, actual={all_assigned})")
    else:
        print(f"  Result: FAIL (expected={test['expected']}, actual={all_assigned})")
    
    # Validate the schedule
    result = constraint.validate(schedule, school)
    if result.violations:
        print("  Violations:")
        for v in result.violations:
            print(f"    - {v.description}")