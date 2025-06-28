#!/usr/bin/env python3
"""Debug why 水1 remains empty for 5組"""

import sys
sys.path.append('.')

from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.config.path_manager import get_path_manager
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.config.constraint_loader import constraint_loader

def analyze_water1():
    print("=== Analyzing 水1 for 5組 classes ===\n")
    
    # Initialize
    path_manager = get_path_manager()
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    
    # Load school data
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # Load current schedule
    schedule = schedule_repo.load_schedule("output.csv", school)
    
    # Load constraints
    constraint_system = UnifiedConstraintSystem()
    all_constraints = constraint_loader.load_all_constraints()
    for constraint in all_constraints:
        constraint_system.register_constraint(constraint)
    
    # Check 水1 for each 5組
    time_slot = TimeSlot("水", 1)
    
    for grade in [1, 2, 3]:
        class_ref = ClassReference(grade, 5)
        print(f"\n{grade}年5組 at 水1:")
        
        # Check what subjects are needed
        base_hours = school.get_all_standard_hours(class_ref)
        print("\n  Subjects still needed:")
        
        # Count current assignments
        current_hours = {}
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                ts = TimeSlot(day, period)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment and assignment.subject:
                    subject = assignment.subject
                    current_hours[subject.name] = current_hours.get(subject.name, 0) + 1
        
        # Show shortage
        for subject, required in base_hours.items():
            current = current_hours.get(subject.name, 0)
            if current < required:
                shortage = required - current
                print(f"    - {subject.name}: need {shortage} more (have {current}/{required})")
        
        # Try each subject and see what constraints prevent it
        print("\n  Checking constraints for each needed subject:")
        
        for subject, required in base_hours.items():
            current = current_hours.get(subject.name, 0)
            if current < required:
                # Get teacher
                teacher = school.get_assigned_teacher(subject, class_ref)
                if teacher:
                    print(f"\n    Trying {subject.name} with {teacher.name}:")
                    
                    # Create test assignment
                    from src.domain.value_objects.assignment import Assignment
                    test_assignment = Assignment(class_ref, subject, teacher)
                    
                    # Check constraints
                    from src.domain.services.unified_constraint_system import AssignmentContext
                    context = AssignmentContext(
                        schedule=schedule,
                        school=school,
                        time_slot=time_slot,
                        assignment=test_assignment
                    )
                    
                    can_assign, violations = constraint_system.check_before_assignment(context)
                    
                    if not can_assign:
                        print(f"      ❌ Cannot assign due to:")
                        for v in violations:
                            print(f"         - {v.description}")
                    else:
                        print(f"      ✅ Could be assigned!")

if __name__ == "__main__":
    analyze_water1()