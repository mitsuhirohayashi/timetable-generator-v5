#!/usr/bin/env python3
"""Debug script to trace gym constraint violations"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.constraints.gym_usage_constraint import GymUsageConstraint
from src.domain.value_objects.time_slot import TimeSlot

def main():
    # Initialize repositories
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # Load school data
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # Load schedule
    schedule = schedule_repo.load_desired_schedule(
        str(path_config.default_output_csv),
        school
    )
    
    # Create constraint
    gym_constraint = GymUsageConstraint()
    
    # Check Wednesday 5th period specifically (where the actual violation is)
    time_slot = TimeSlot("水", 5)
    assignments = schedule.get_assignments_by_time_slot(time_slot)
    
    print(f"\n=== Checking {time_slot} ===")
    print(f"Total assignments: {len(assignments)}")
    
    # List all PE assignments
    pe_assignments = [a for a in assignments if a.subject.name == "保"]
    print(f"\nPE assignments found: {len(pe_assignments)}")
    for a in pe_assignments:
        print(f"  - {a.class_ref}: {a.subject.name}")
    
    # Count PE groups
    pe_groups = gym_constraint._count_pe_groups(assignments)
    print(f"\nPE groups counted: {pe_groups}")
    
    # Detailed group analysis
    print("\nDetailed group analysis:")
    pe_classes = set()
    counted_groups = set()
    
    for assignment in assignments:
        if assignment.subject.name == "保":
            class_ref = assignment.class_ref
            print(f"\nProcessing {class_ref}:")
            
            if class_ref in counted_groups:
                print(f"  - Already counted")
                continue
            
            if class_ref in gym_constraint.exchange_parent_map:
                parent_class = gym_constraint.exchange_parent_map[class_ref]
                print(f"  - Exchange class, parent is {parent_class}")
                parent_has_pe = any(a.class_ref == parent_class and a.subject.name == "保" 
                                   for a in assignments)
                print(f"  - Parent has PE: {parent_has_pe}")
                if parent_has_pe:
                    counted_groups.add(class_ref)
                    counted_groups.add(parent_class)
                    pe_classes.add(f"{parent_class}+{class_ref}")
                    print(f"  - Grouped as: {parent_class}+{class_ref}")
                else:
                    counted_groups.add(class_ref)
                    pe_classes.add(str(class_ref))
                    print(f"  - Counted as separate group")
            elif class_ref in gym_constraint.exchange_parent_map.values():
                print(f"  - Parent class")
                # Find exchange class
                exchange_class = None
                for exc, par in gym_constraint.exchange_parent_map.items():
                    if par == class_ref:
                        exchange_class = exc
                        break
                print(f"  - Exchange class is {exchange_class}")
                if exchange_class:
                    exchange_has_pe = any(a.class_ref == exchange_class and a.subject.name == "保" 
                                        for a in assignments)
                    print(f"  - Exchange has PE: {exchange_has_pe}")
                    if exchange_has_pe:
                        if exchange_class not in counted_groups:
                            counted_groups.add(class_ref)
                            counted_groups.add(exchange_class)
                            pe_classes.add(f"{class_ref}+{exchange_class}")
                            print(f"  - Grouped as: {class_ref}+{exchange_class}")
                        else:
                            print(f"  - Exchange class already counted")
                    else:
                        counted_groups.add(class_ref)
                        pe_classes.add(str(class_ref))
                        print(f"  - Counted as separate group")
            else:
                print(f"  - Regular class")
                counted_groups.add(class_ref)
                pe_classes.add(str(class_ref))
                print(f"  - Counted as separate group")
    
    print(f"\nFinal PE groups: {pe_classes}")
    print(f"Total groups: {len(pe_classes)}")
    
    # Validate
    result = gym_constraint.validate(schedule, school)
    if result.violations:
        print("\nViolations found:")
        for v in result.violations:
            print(f"  - {v.description}")
    else:
        print("\nNo violations found")
    
    # Now let's trace how these assignments were made
    print("\n\n=== Tracing assignment order ===")
    # Look at all PE assignments in the schedule
    all_pe_assignments = []
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            ts = TimeSlot(day, period)
            assigns = schedule.get_assignments_by_time_slot(ts)
            for a in assigns:
                if a.subject.name == "保":
                    all_pe_assignments.append((ts, a))
    
    print(f"\nTotal PE assignments in schedule: {len(all_pe_assignments)}")
    for ts, a in sorted(all_pe_assignments, key=lambda x: (x[0].day, x[0].period)):
        print(f"  - {ts}: {a.class_ref}")

if __name__ == "__main__":
    main()