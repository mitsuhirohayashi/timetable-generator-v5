#!/usr/bin/env python3
"""Debug script to find the teacher absence constraint issue"""
import sys
from pathlib import Path

# Add timetable_v5 to path
sys.path.insert(0, str(Path(__file__).parent))

from src.domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.config.path_config import path_config

def main():
    print("Testing TeacherAbsenceConstraint...")
    
    # Load school data
    school_repo = CSVSchoolRepository(path_config.data_dir)
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # Create empty schedule
    schedule = Schedule()
    
    # Create constraint with no absence loader
    constraint = TeacherAbsenceConstraint()
    
    try:
        # Call validate
        result = constraint.validate(schedule, school)
        print(f"Validation completed successfully. Violations: {len(result.violations)}")
        
        # Print any violations
        for violation in result.violations:
            print(f"Violation: {violation}")
            print(f"  time_slot type: {type(violation.time_slot)}")
            print(f"  time_slot value: {violation.time_slot}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()