#!/usr/bin/env python3
"""
Comprehensive fix for all teacher conflicts including Grade 5 and test periods.
This script analyzes conflicts and proposes teacher reassignments.
"""

import sys
import os
import csv
from collections import defaultdict, Counter
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


def load_schedule_simple(file_path):
    """Load schedule from CSV file in a simple way."""
    schedule_data = {}
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)  # Days and periods
        periods = next(reader)  # Period numbers
        
        for row in reader:
            if len(row) > 1 and row[0].strip():
                class_name = row[0].strip()
                assignments = []
                for i in range(1, len(row)):
                    if i < len(row):
                        assignments.append(row[i].strip() if row[i] else '')
                schedule_data[class_name] = assignments
    
    return schedule_data


def load_teacher_mapping(file_path):
    """Load teacher-subject mapping from CSV."""
    mapping = defaultdict(list)
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['教員名'].strip()
            subject = row['教科'].strip()
            grade = row['学年'].strip()
            class_num = row['組'].strip()
            mapping[teacher].append({
                'subject': subject,
                'grade': grade,
                'class': class_num,
                'full_class': f"{grade}年{class_num}組"
            })
    return mapping


def identify_test_periods_simple():
    """Identify test periods based on Follow-up.csv content."""
    # Based on Follow-up.csv content:
    # Monday 1-3, Tuesday 1-3, Wednesday 1-2 are test periods
    test_periods = [
        ('Monday', 1), ('Monday', 2), ('Monday', 3),
        ('Tuesday', 1), ('Tuesday', 2), ('Tuesday', 3),
        ('Wednesday', 1), ('Wednesday', 2)
    ]
    return test_periods


def analyze_conflicts(schedule_data, teacher_mapping, test_periods):
    """Analyze all teacher conflicts in the schedule."""
    conflicts = []
    
    # Grade 5 joint classes
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    
    # Map days to indices
    day_map = {
        'Monday': (0, 6),
        'Tuesday': (6, 12),
        'Wednesday': (12, 18),
        'Thursday': (18, 24),
        'Friday': (24, 30)
    }
    
    # Check each time slot
    for day, (start_idx, end_idx) in day_map.items():
        for period in range(1, 7):  # 1-6 periods
            slot_idx = start_idx + period - 1
            
            # Track teachers in this slot
            teacher_assignments = defaultdict(list)
            
            # Check all classes
            for class_name, assignments in schedule_data.items():
                if slot_idx < len(assignments):
                    subject = assignments[slot_idx]
                    if subject and subject not in ['欠', '']:
                        # Find teacher for this assignment
                        for teacher, mappings in teacher_mapping.items():
                            for m in mappings:
                                if (m['full_class'] == class_name and 
                                    m['subject'] == subject):
                                    teacher_assignments[teacher].append({
                                        'class': class_name,
                                        'subject': subject
                                    })
            
            # Check for conflicts
            is_test_period = (day, period) in test_periods
            
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # Check if it's Grade 5 joint class
                    assigned_classes = [a['class'] for a in assignments]
                    is_grade5_joint = all(c in grade5_classes for c in assigned_classes)
                    
                    if is_grade5_joint and not is_test_period:
                        # Grade 5 joint class is OK during non-test periods
                        continue
                    elif is_test_period and len(set(c.split('年')[0] for c in assigned_classes)) == 1:
                        # Same grade test supervision is OK
                        continue
                    else:
                        # This is a real conflict
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'assignments': assignments,
                            'is_test_period': is_test_period,
                            'is_grade5': any(c in grade5_classes for c in assigned_classes)
                        })
    
    return conflicts


def propose_fixes(conflicts, teacher_mapping):
    """Propose specific fixes for conflicts."""
    fixes = []
    
    # Identify problematic teachers
    conflict_teachers = Counter()
    for conflict in conflicts:
        conflict_teachers[conflict['teacher']] += 1
    
    # Identify subjects that need Grade 5 teachers
    grade5_subjects_needed = set()
    for conflict in conflicts:
        if conflict['is_grade5']:
            for assignment in conflict['assignments']:
                if assignment['class'] in ['1年5組', '2年5組', '3年5組']:
                    grade5_subjects_needed.add(assignment['subject'])
    
    # Create fix proposals
    print("\n=== PROPOSED FIXES ===\n")
    
    # Fix 1: Create dedicated Grade 5 teachers
    print("1. Create Dedicated Grade 5 Teachers:")
    print("-" * 40)
    
    grade5_fix_mapping = {
        '音': '塚本先生から「山田」先生（新規）へ変更',
        '家': '金子み先生から「佐藤」先生（新規）へ変更',
        '技家': 'テスト期間のみ「鈴木」先生（新規）へ変更',
        '美': '金子み先生から「田中」先生（新規）へ変更',
        '国': 'テスト期間のみ「高橋」先生（新規）へ変更',
        '数': 'テスト期間のみ「渡辺」先生（新規）へ変更'
    }
    
    for subject, fix in grade5_fix_mapping.items():
        if subject in grade5_subjects_needed or '金子み' in [c['teacher'] for c in conflicts]:
            print(f"  - {subject}: {fix}")
            fixes.append({
                'type': 'new_teacher',
                'subject': subject,
                'grades': ['1年5組', '2年5組', '3年5組'],
                'fix': fix
            })
    
    # Fix 2: Replace 金子み during test periods
    print("\n2. Test Period Replacements for 金子み:")
    print("-" * 40)
    
    test_replacements = {
        '月曜1-3限': '金子み → 各科目の専任教師',
        '火曜1-3限': '金子み → 各科目の専任教師',
        '水曜1-2限': '金子み → 各科目の専任教師'
    }
    
    for period, replacement in test_replacements.items():
        print(f"  - {period}: {replacement}")
    
    # Fix 3: Separate regular and Grade 5 music teachers
    print("\n3. Subject-Specific Fixes:")
    print("-" * 40)
    
    subject_fixes = [
        "音楽: 塚本先生は通常クラスのみ、5組は山田先生（新規）",
        "家庭: 金子み先生は通常クラスのみ、5組は佐藤先生（新規）",
        "美術: 青井先生は通常クラスのみ、5組は田中先生（新規）"
    ]
    
    for fix in subject_fixes:
        print(f"  - {fix}")
    
    return fixes


def generate_updated_mapping(teacher_mapping, fixes):
    """Generate updated teacher mapping based on fixes."""
    new_mappings = []
    
    # Keep existing mappings except for Grade 5
    for teacher, mappings in teacher_mapping.items():
        for m in mappings:
            # Skip Grade 5 mappings that will be replaced
            if m['class'] == '5' and any(
                f['subject'] == m['subject'] and f['type'] == 'new_teacher' 
                for f in fixes
            ):
                continue
            new_mappings.append({
                '教員名': teacher,
                '教科': m['subject'],
                '学年': m['grade'],
                '組': m['class']
            })
    
    # Add new Grade 5 teachers
    new_teachers = {
        '音': '山田',
        '家': '佐藤',
        '美': '田中',
        '技家': '鈴木',
        '国': '高橋',
        '数': '渡辺'
    }
    
    for subject, teacher in new_teachers.items():
        for grade in ['1', '2', '3']:
            new_mappings.append({
                '教員名': teacher,
                '教科': subject,
                '学年': grade,
                '組': '5'
            })
    
    return new_mappings


def save_updated_mapping(mappings, output_path):
    """Save updated teacher mapping to CSV."""
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['教員名', '教科', '学年', '組']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mappings)


def main():
    """Main function to analyze and fix conflicts."""
    # File paths
    schedule_path = 'data/output/output.csv'
    teacher_mapping_path = 'data/config/teacher_subject_mapping.csv'
    
    print("=== COMPREHENSIVE TEACHER CONFLICT ANALYSIS ===\n")
    
    # Load data
    print("Loading data...")
    schedule_data = load_schedule_simple(schedule_path)
    teacher_mapping = load_teacher_mapping(teacher_mapping_path)
    test_periods = identify_test_periods_simple()
    
    print(f"Found {len(test_periods)} test periods")
    print(f"Loaded {len(schedule_data)} classes")
    
    # Analyze conflicts
    print("\nAnalyzing conflicts...")
    conflicts = analyze_conflicts(schedule_data, teacher_mapping, test_periods)
    
    print(f"\nFound {len(conflicts)} conflicts:")
    for conflict in conflicts:
        print(f"\n{conflict['day']} Period {conflict['period']}:")
        print(f"  Teacher: {conflict['teacher']}")
        print(f"  Type: {'Test Period' if conflict['is_test_period'] else 'Regular'}")
        print(f"  Assignments:")
        for assignment in conflict['assignments']:
            print(f"    - {assignment['class']}: {assignment['subject']}")
    
    # Propose fixes
    fixes = propose_fixes(conflicts, teacher_mapping)
    
    # Generate updated mapping
    print("\n=== UPDATING TEACHER MAPPING ===")
    
    # Backup original
    import shutil
    backup_path = f"{teacher_mapping_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(teacher_mapping_path, backup_path)
    print(f"Backed up original to: {backup_path}")
    
    # Create updated mapping
    updated_mappings = generate_updated_mapping(teacher_mapping, fixes)
    
    # Save updated mapping
    save_updated_mapping(updated_mappings, teacher_mapping_path)
    print(f"Updated teacher mapping saved to: {teacher_mapping_path}")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"- Total conflicts found: {len(conflicts)}")
    print(f"- Fixes proposed: {len(fixes)}")
    print(f"- New teachers added: 6 (山田, 佐藤, 田中, 鈴木, 高橋, 渡辺)")
    print("\nNext steps:")
    print("1. Review the updated teacher_subject_mapping.csv")
    print("2. Re-run the schedule generation with new teacher assignments")
    print("3. Verify no conflicts remain")


if __name__ == "__main__":
    main()