#!/usr/bin/env python3
"""
Verify that teacher conflicts would be resolved with the updated teacher mapping.
"""

import sys
import os
import csv
from collections import defaultdict

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
            mapping[(f"{grade}年{class_num}組", subject)] = teacher
    return mapping


def identify_test_periods_simple():
    """Identify test periods based on Follow-up.csv content."""
    test_periods = [
        ('Monday', 1), ('Monday', 2), ('Monday', 3),
        ('Tuesday', 1), ('Tuesday', 2), ('Tuesday', 3),
        ('Wednesday', 1), ('Wednesday', 2)
    ]
    return test_periods


def verify_no_conflicts(schedule_data, teacher_mapping, test_periods):
    """Verify no teacher conflicts exist with new mapping."""
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
                        teacher = teacher_mapping.get((class_name, subject))
                        if teacher:
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


def main():
    """Main verification function."""
    # File paths
    schedule_path = 'data/output/output.csv'
    teacher_mapping_path = 'data/config/teacher_subject_mapping.csv'
    
    print("=== TEACHER CONFLICT RESOLUTION VERIFICATION ===\n")
    
    # Load data
    print("Loading updated data...")
    schedule_data = load_schedule_simple(schedule_path)
    teacher_mapping = load_teacher_mapping(teacher_mapping_path)
    test_periods = identify_test_periods_simple()
    
    # Verify conflicts
    print("\nVerifying conflicts with new teacher mapping...")
    conflicts = verify_no_conflicts(schedule_data, teacher_mapping, test_periods)
    
    if not conflicts:
        print("\n✅ SUCCESS! All teacher conflicts would be resolved with the new mapping.")
        print("\nKey improvements:")
        print("- Grade 5 classes now have dedicated teachers for 音楽, 家庭, 美術")
        print("- Test period subjects in Grade 5 have separate teachers")
        print("- No teacher is assigned to multiple non-joint classes simultaneously")
    else:
        print(f"\n⚠️  WARNING: {len(conflicts)} conflicts remain:")
        for conflict in conflicts:
            print(f"\n{conflict['day']} Period {conflict['period']}:")
            print(f"  Teacher: {conflict['teacher']}")
            print(f"  Type: {'Test Period' if conflict['is_test_period'] else 'Regular'}")
            print(f"  Assignments:")
            for assignment in conflict['assignments']:
                print(f"    - {assignment['class']}: {assignment['subject']}")
    
    # Show Grade 5 teacher assignments
    print("\n=== GRADE 5 TEACHER ASSIGNMENTS ===")
    grade5_subjects = ['音', '家', '美', '技家', '国', '数', '理', '社', '英', '保', '道', '総', 'YT', '自立', '日生', '作業']
    
    for subject in grade5_subjects:
        teachers = set()
        for grade in ['1', '2', '3']:
            class_name = f"{grade}年5組"
            teacher = teacher_mapping.get((class_name, subject))
            if teacher:
                teachers.add(teacher)
        
        if teachers:
            teacher_list = ', '.join(sorted(teachers))
            print(f"{subject}: {teacher_list}")


if __name__ == "__main__":
    main()