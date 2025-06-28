#!/usr/bin/env python3
"""
Real teacher conflict fixer focusing on non-test period conflicts.
Proposes minimal changes to teacher assignments to resolve conflicts.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser


def analyze_teacher_conflicts(schedule_path, teacher_mapping_path, followup_path):
    """Analyze teacher conflicts excluding test periods."""
    
    # Load data
    reader = CSVScheduleReader()
    schedule = reader.read(schedule_path)
    
    # Parse follow-up for test periods
    parser = EnhancedFollowUpParser(followup_path.parent)
    followup_data = parser.parse_file(followup_path.name)
    test_periods = followup_data.get('test_periods', [])
    
    # Load teacher mapping
    df = pd.read_csv(teacher_mapping_path, encoding='utf-8-sig')
    teacher_mapping = {}
    
    for _, row in df.iterrows():
        subject = row['教科']
        teacher = row['教員名']
        grade = row['学年']
        class_num = row['組']
        
        if pd.isna(subject) or pd.isna(teacher):
            continue
            
        class_id = f"{int(grade)}年{int(class_num)}組"
        
        if subject not in teacher_mapping:
            teacher_mapping[subject] = {}
        if class_id not in teacher_mapping[subject]:
            teacher_mapping[subject][class_id] = []
        if teacher not in teacher_mapping[subject][class_id]:
            teacher_mapping[subject][class_id].append(teacher)
    
    # Build teacher assignment mapping
    teacher_assignments = {}
    for slot, assignment in schedule.get_all_assignments():
        if assignment.subject.name in ['欠', 'YT', '道', '学', '総', '学総', '行']:
            continue
            
        # Skip test periods
        is_test = False
        for test in test_periods:
            if test.day == slot.day and slot.period in test.periods:
                is_test = True
                break
        if is_test:
            continue
        
        # Get teachers for this assignment
        class_id = str(assignment.class_ref)
        teachers = teacher_mapping.get(assignment.subject.name, {}).get(class_id, [])
        if not teachers:
            continue
            
        key = (slot.day, slot.period)
        if key not in teacher_assignments:
            teacher_assignments[key] = {}
            
        for teacher in teachers:
            if teacher not in teacher_assignments[key]:
                teacher_assignments[key][teacher] = []
            teacher_assignments[key][teacher].append(class_id)
    
    # Find conflicts
    conflicts = []
    for (day, period), teachers in teacher_assignments.items():
        for teacher, classes in teachers.items():
            if len(classes) > 1:
                # Special case: Grade 5 joint classes are OK
                if set(classes).issubset({'1年5組', '2年5組', '3年5組'}):
                    continue
                    
                conflicts.append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'classes': classes,
                    'count': len(classes)
                })
    
    return conflicts


def propose_solutions(conflicts, teacher_mapping_path):
    """Propose solutions for teacher conflicts."""
    
    # Load current mapping
    df = pd.read_csv(teacher_mapping_path, encoding='utf-8-sig')
    
    solutions = []
    new_teachers = {}
    
    # Analyze conflicts by teacher and subject
    teacher_stats = {}
    for conflict in conflicts:
        teacher = conflict['teacher']
        if teacher not in teacher_stats:
            teacher_stats[teacher] = {
                'total_conflicts': 0,
                'max_simultaneous': 0,
                'subjects': set(),
                'conflict_details': []
            }
        
        teacher_stats[teacher]['total_conflicts'] += 1
        teacher_stats[teacher]['max_simultaneous'] = max(
            teacher_stats[teacher]['max_simultaneous'], 
            conflict['count']
        )
        
        # Find subjects this teacher teaches
        teacher_rows = df[df['教員名'] == teacher]
        for _, row in teacher_rows.iterrows():
            if pd.notna(row['教科']):
                teacher_stats[teacher]['subjects'].add(row['教科'])
        
        teacher_stats[teacher]['conflict_details'].append(conflict)
    
    # Propose solutions based on conflict patterns
    for teacher, stats in teacher_stats.items():
        if teacher == '塚本' and '音' in stats['subjects']:
            # Music teacher conflict
            # Check if Grade 5 is involved in any conflicts
            has_grade5_conflict = False
            for detail in stats['conflict_details']:
                if any('5組' in c for c in detail['classes']):
                    has_grade5_conflict = True
                    break
                    
            if has_grade5_conflict or stats['max_simultaneous'] >= 3:
                solutions.append({
                    'type': 'add_teacher',
                    'current_teacher': '塚本',
                    'subject': '音',
                    'new_teacher': '山田',  # Already exists for Grade 5
                    'action': 'Have 山田先生 handle ALL Grade 5 music classes independently',
                    'reason': f'塚本先生 has {stats["total_conflicts"]} conflicts teaching up to {stats["max_simultaneous"]} classes simultaneously'
                })
                
                # Remove 塚本 from Grade 5 music
                new_teachers['remove'] = new_teachers.get('remove', [])
                new_teachers['remove'].extend([
                    {'教員名': '塚本', '教科': '音', '学年': 1, '組': 5},
                    {'教員名': '塚本', '教科': '音', '学年': 2, '組': 5},
                    {'教員名': '塚本', '教科': '音', '学年': 3, '組': 5}
                ])
            
        elif teacher == '金子み' and '家' in stats['subjects']:
            # Home economics conflict
            has_grade5_conflict = False
            for detail in stats['conflict_details']:
                if any('5組' in c for c in detail['classes']):
                    has_grade5_conflict = True
                    break
                    
            if has_grade5_conflict:
                solutions.append({
                    'type': 'reassign',
                    'current_teacher': '金子み',
                    'subject': '家',
                    'new_teacher': '佐藤',  # Already exists for Grade 5
                    'action': 'Have 佐藤先生 handle ALL Grade 5 home economics independently',
                    'reason': f'金子み先生 cannot teach both regular classes and Grade 5 joint classes simultaneously'
                })
                
                # Remove 金子み from Grade 5 home economics (keep regular classes)
                new_teachers['remove'] = new_teachers.get('remove', [])
                new_teachers['remove'].extend([
                    {'教員名': '金子み', '教科': '家', '学年': 1, '組': 5},
                    {'教員名': '金子み', '教科': '家', '学年': 2, '組': 5},
                    {'教員名': '金子み', '教科': '家', '学年': 3, '組': 5}
                ])
            
        # For teachers with 3+ simultaneous classes, suggest specific solutions
        elif stats['max_simultaneous'] >= 3:
            solutions.append({
                'type': 'major_conflict',
                'teacher': teacher,
                'subject': list(stats['subjects'])[0] if stats['subjects'] else 'unknown',
                'action': f'Consider adding an assistant teacher or redistributing {teacher}先生\'s classes',
                'reason': f'{teacher}先生 has {stats["total_conflicts"]} conflicts with up to {stats["max_simultaneous"]} simultaneous classes',
                'details': stats['conflict_details']
            })
        else:
            # For other conflicts, suggest schedule adjustments
            for detail in stats['conflict_details'][:1]:  # Only show first conflict to avoid clutter
                solutions.append({
                    'type': 'schedule_adjustment',
                    'teacher': teacher,
                    'day': detail['day'],
                    'period': detail['period'],
                    'classes': detail['classes'],
                    'action': f'Move one of the classes to a different time slot',
                    'reason': f'{teacher}先生 cannot teach {detail["count"]} classes simultaneously'
                })
    
    return solutions, new_teachers


def apply_changes(teacher_mapping_path, new_teachers):
    """Apply proposed changes to teacher mapping."""
    
    # Create backup
    backup_path = teacher_mapping_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df = pd.read_csv(teacher_mapping_path, encoding='utf-8-sig')
    df.to_csv(backup_path, index=False, encoding='utf-8-sig')
    print(f"\nCreated backup: {backup_path}")
    
    # Apply removals
    if 'remove' in new_teachers:
        for removal in new_teachers['remove']:
            mask = (
                (df['教員名'] == removal['教員名']) & 
                (df['教科'] == removal['教科']) & 
                (df['学年'] == removal['学年']) & 
                (df['組'] == removal['組'])
            )
            df = df[~mask]
            print(f"Removed: {removal['教員名']} teaching {removal['教科']} for {removal['学年']}年{removal['組']}組")
    
    # Save updated mapping
    df.to_csv(teacher_mapping_path, index=False, encoding='utf-8-sig')
    print(f"\nUpdated teacher mapping saved to: {teacher_mapping_path}")


def main():
    # Define paths
    schedule_path = project_root / 'data' / 'output' / 'output.csv'
    teacher_mapping_path = project_root / 'data' / 'config' / 'teacher_subject_mapping.csv'
    followup_path = project_root / 'data' / 'input' / 'Follow-up.csv'
    
    print("=== Real Teacher Conflict Analysis ===")
    print("Analyzing non-test period conflicts...\n")
    
    # Analyze conflicts
    conflicts = analyze_teacher_conflicts(schedule_path, teacher_mapping_path, followup_path)
    
    if not conflicts:
        print("No teacher conflicts found in non-test periods!")
        return
    
    # Sort conflicts by severity
    conflicts.sort(key=lambda x: (-x['count'], x['teacher'], x['day'], x['period']))
    
    print(f"Found {len(conflicts)} teacher conflicts:\n")
    
    # Group by teacher
    by_teacher = {}
    for conflict in conflicts:
        teacher = conflict['teacher']
        if teacher not in by_teacher:
            by_teacher[teacher] = []
        by_teacher[teacher].append(conflict)
    
    # Display conflicts
    for teacher, teacher_conflicts in by_teacher.items():
        print(f"\n{teacher}先生:")
        for c in teacher_conflicts:
            print(f"  - {c['day']} P{c['period']}: Teaching {c['count']} classes: {', '.join(c['classes'])}")
    
    # Propose solutions
    print("\n\n=== Proposed Solutions ===")
    solutions, new_teachers = propose_solutions(conflicts, teacher_mapping_path)
    
    for i, solution in enumerate(solutions, 1):
        print(f"\n{i}. {solution['type'].upper()}")
        print(f"   Teacher: {solution.get('current_teacher', solution.get('teacher'))}")
        if 'subject' in solution:
            print(f"   Subject: {solution['subject']}")
        print(f"   Action: {solution['action']}")
        print(f"   Reason: {solution['reason']}")
    
    # Summary of changes
    print("\n\n=== Summary of Teacher Mapping Changes ===")
    if 'remove' in new_teachers:
        print("\nRemovals from teacher_subject_mapping.csv:")
        for removal in new_teachers['remove']:
            print(f"  - Remove {removal['教員名']} from {removal['教科']} for {removal['学年']}年{removal['組']}組")
    
    print("\nKey changes:")
    print("1. 山田先生 will handle ALL Grade 5 music classes (not 塚本先生)")
    print("2. 佐藤先生 will handle ALL Grade 5 home economics (not 金子み先生)")
    print("3. This separates Grade 5 joint classes from regular classes")
    
    # Ask for confirmation
    print("\n" + "="*50)
    response = input("\nApply these changes to teacher_subject_mapping.csv? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        apply_changes(teacher_mapping_path, new_teachers)
        print("\nChanges applied successfully!")
        print("\nNext steps:")
        print("1. Regenerate the schedule with: python3 main.py generate")
        print("2. Check for remaining conflicts with: python3 scripts/analysis/check_violations.py")
    else:
        print("\nNo changes were made.")
        print("You can manually edit teacher_subject_mapping.csv if needed.")


if __name__ == "__main__":
    main()