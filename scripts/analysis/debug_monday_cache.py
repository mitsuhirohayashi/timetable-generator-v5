#!/usr/bin/env python3
"""Debug Monday duplicate issues - check caching behavior."""

import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import ScheduleCSVRepository
from src.infrastructure.di_container import get_unified_constraint_system
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.domain.services.validators.unified_constraint_validator import UnifiedConstraintValidator


def check_monday_cache_behavior():
    """Check if caching is causing Monday duplicate issues."""
    
    # Load schedule
    repo = ScheduleCSVRepository()
    school, schedule, _ = repo.load_schedule()
    
    # Create validator
    constraint_system = get_unified_constraint_system()
    validator = UnifiedConstraintValidator(constraint_system)
    
    print("Testing cache behavior for Monday duplicates")
    print("=" * 60)
    
    # Test case: 1年2組
    test_class = next(c for c in school.get_all_classes() if str(c) == "1年2組")
    
    # Check existing Monday subjects
    monday_subjects = []
    for period in range(1, 7):
        time_slot = TimeSlot("月", period)
        assignment = schedule.get_assignment(time_slot, test_class)
        if assignment:
            monday_subjects.append(f"{period}限: {assignment.subject.name}")
    
    print(f"\n1年2組の月曜日の授業:")
    for subj in monday_subjects:
        print(f"  {subj}")
    
    # Test daily count function
    print("\n日内カウントテスト:")
    subjects_to_check = ["国", "社", "理", "数", "英"]
    
    for subject_name in subjects_to_check:
        # Find the subject object
        subject = next((s for s in school.get_all_subjects() if s.name == subject_name), None)
        if not subject:
            continue
            
        # Check without cache
        validator.clear_cache()
        count1 = validator._get_daily_subject_count_cached(schedule, test_class, "月", subject)
        
        # Check with cache
        count2 = validator._get_daily_subject_count_cached(schedule, test_class, "月", subject)
        
        print(f"  {subject_name}: count={count1} (cache cleared), count={count2} (with cache)")
        
        # Check cache stats
        stats = validator.get_statistics()
        print(f"    Cache stats: hits={stats['cache_hits']}, misses={stats['cache_misses']}")
    
    # Test constraint checking for duplicates
    print("\n\n制約チェックテスト:")
    print("既存の「国」の位置に別の「国」を配置できるかテスト")
    
    # Try to place another 国 in an empty slot
    koku_subject = next((s for s in school.get_all_subjects() if s.name == "国"), None)
    teacher = next((t for t in school.get_all_teachers() if t.name == "寺田"), None)
    
    if koku_subject and teacher:
        # Find an empty slot on Monday
        for period in range(1, 7):
            time_slot = TimeSlot("月", period)
            existing = schedule.get_assignment(time_slot, test_class)
            if not existing:
                print(f"\n月曜{period}限（空き）に「国」を配置テスト:")
                
                test_assignment = Assignment(test_class, koku_subject, teacher)
                
                # Test with different check levels
                for check_level in ['strict', 'normal', 'relaxed']:
                    validator.clear_cache()
                    can_place, error = validator.can_place_assignment(
                        schedule, school, time_slot, test_assignment, check_level
                    )
                    print(f"  {check_level}: {can_place} - {error if error else 'OK'}")
                
                break
    
    # Check actual constraint implementation
    print("\n\n実装詳細:")
    print("DailyDuplicateConstraint._get_max_allowed() returns:", 1)
    print("これは全教科1日1回までという制約です")
    
    # Test the actual filled slots from output
    print("\n\noutput.csvの1年2組月曜日の重複:")
    output_df = pd.read_csv('data/output/output.csv', encoding='utf-8')
    row_idx = 3  # 1年2組
    monday_subjects_output = []
    for col in range(1, 7):
        subj = output_df.iloc[row_idx, col]
        if pd.notna(subj) and subj != '':
            monday_subjects_output.append(subj)
    
    from collections import Counter
    counts = Counter(monday_subjects_output)
    for subj, count in counts.items():
        if count > 1:
            print(f"  {subj}: {count}回 （違反）")


if __name__ == '__main__':
    check_monday_cache_behavior()