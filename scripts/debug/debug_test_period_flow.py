#!/usr/bin/env python3
"""Debug test period flow - understand how test periods are being overwritten."""

import sys
import pandas as pd
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser

def analyze_test_period_flow():
    """Analyze how test periods are handled in the system."""
    
    # 1. Load test period information
    print("=== 1. Loading Test Period Information ===")
    input_dir = Path("data/input")
    
    # Try natural parser
    natural_parser = NaturalFollowUpParser(input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    if natural_result["parse_success"] and "test_periods" in natural_result:
        print(f"Natural parser found test periods: {natural_result['test_periods']}")
    else:
        print("Natural parser did not find test periods")
    
    # Try enhanced parser
    from src.infrastructure.di_container import get_followup_parser
    enhanced_parser = get_followup_parser()
    test_periods = enhanced_parser.parse_test_periods()
    
    print(f"\nEnhanced parser found {len(test_periods)} test period entries:")
    for tp in test_periods:
        if hasattr(tp, 'day') and hasattr(tp, 'periods'):
            print(f"  - {tp.day}曜日: {tp.periods}時限")
        else:
            print(f"  - {tp}")
    
    # 2. Check input.csv for test period data
    print("\n=== 2. Checking Input.csv Test Period Data ===")
    input_csv = pd.read_csv("data/input/input.csv", header=[0, 1])
    
    # Test periods: 月1-3, 火1-3, 水1-2
    test_slots = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    # Count non-empty cells in test periods
    test_data_count = 0
    water2_data = {}
    
    for day, period in test_slots:
        col = (day, str(period))
        if col in input_csv.columns:
            for idx, class_name in enumerate(input_csv.iloc[:, 0]):
                if pd.notna(class_name) and class_name != "":
                    val = input_csv.loc[idx, col]
                    if pd.notna(val) and val != "":
                        test_data_count += 1
                        if day == "水" and period == 2:
                            water2_data[class_name] = val
    
    print(f"Total test period cells with data in input.csv: {test_data_count}")
    print(f"\nWater column 2 (水曜2限) data:")
    for class_name, subject in water2_data.items():
        print(f"  {class_name}: {subject}")
    
    # 3. Check if test periods are locked
    print("\n=== 3. Checking Test Period Protection ===")
    
    # Create a simple test
    schedule = Schedule()
    
    # Try to lock a test period cell
    test_slot = TimeSlot("水", 2)
    test_class = ClassReference(2, 2)  # 2年2組
    
    print(f"\nTesting lock mechanism for {test_class.full_name} at {test_slot}:")
    print(f"  Is locked before: {schedule.is_locked(test_slot, test_class)}")
    
    schedule.lock_cell(test_slot, test_class)
    print(f"  Is locked after: {schedule.is_locked(test_slot, test_class)}")
    
    # Try to assign to a locked cell
    from src.domain.value_objects.assignment import Assignment
    from src.domain.entities.school import Subject, Teacher
    
    try:
        test_assignment = Assignment(
            test_class,
            Subject("国", "国語"),
            Teacher("Test", "テスト先生")
        )
        schedule.assign(test_slot, test_assignment)
        print("  ERROR: Assignment succeeded on locked cell!")
    except Exception as e:
        print(f"  Good: Assignment failed with error: {e}")
    
    # 4. Check CSP orchestrator flow
    print("\n=== 4. CSP Orchestrator Flow ===")
    print("The CSP orchestrator should:")
    print("1. Load test periods from followup parser")
    print("2. Lock all existing assignments (including test periods)")
    print("3. Call TestPeriodProtector.protect_test_periods()")
    print("4. These locked cells should not be modified")
    
    # 5. Recommendations
    print("\n=== 5. Recommendations ===")
    print("The issue appears to be that test period cells are being overwritten.")
    print("Possible causes:")
    print("1. Test period cells are not being locked properly")
    print("2. The lock is being ignored during assignment")
    print("3. The schedule is being modified after locking")
    print("\nThe water column 2 violations suggest that assignments are happening")
    print("despite test period protection.")

if __name__ == "__main__":
    analyze_test_period_flow()