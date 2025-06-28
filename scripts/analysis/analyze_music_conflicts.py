#!/usr/bin/env python3
"""Analyze music teacher conflicts"""

import pandas as pd
from collections import defaultdict
from pathlib import Path

# Load data
schedule_df = pd.read_csv('data/output/output.csv', encoding='utf-8-sig')
teacher_df = pd.read_csv('data/config/teacher_subject_mapping.csv', encoding='utf-8-sig')

# Build teacher mapping
teacher_map = defaultdict(lambda: defaultdict(list))
for _, row in teacher_df.iterrows():
    if pd.notna(row['教科']) and pd.notna(row['教員名']):
        class_id = f"{int(row['学年'])}年{int(row['組'])}組"
        teacher_map[row['教科']][class_id].append(row['教員名'])

# Find conflicts
days = ['月', '火', '水', '木', '金']
conflicts = []

for day_idx, day in enumerate(days):
    for period in range(1, 7):
        # Track teachers at this time
        teacher_classes = defaultdict(list)
        
        for idx, row in schedule_df.iterrows():
            class_name = row.iloc[0] if pd.notna(row.iloc[0]) else ''
            if not class_name or class_name == '基本時間割' or not class_name.endswith('組'):
                continue
                
            col_idx = day_idx * 6 + period + 1
            if col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                subject = row.iloc[col_idx]
                if subject in ['欠', 'YT', '道', '学', '総', '学総', '行', '技家']:
                    continue
                    
                # Get teachers for this subject and class
                teachers = teacher_map[subject][class_name]
                for teacher in teachers:
                    teacher_classes[teacher].append((class_name, subject))
        
        # Find conflicts
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # Check if it's Grade 5 joint classes
                classes = [a[0] for a in assignments]
                if set(classes).issubset({'1年5組', '2年5組', '3年5組'}):
                    continue
                conflicts.append({
                    'teacher': teacher,
                    'day': day,
                    'period': period,
                    'assignments': assignments
                })

# Sort and display conflicts
conflicts.sort(key=lambda x: (x['teacher'], x['day'], x['period']))

print('Real Teacher Conflicts (excluding test periods):')
print('=' * 60)

current_teacher = None
for conflict in conflicts:
    if conflict['teacher'] != current_teacher:
        if current_teacher:
            print()
        current_teacher = conflict['teacher']
        print(f"{current_teacher}先生:")
    
    classes_str = ', '.join([f'{a[0]}({a[1]})' for a in conflict['assignments']])
    print(f"  - {conflict['day']} P{conflict['period']}: {classes_str}")

# Summary
print(f"\nTotal conflicts found: {len(conflicts)}")

# Check specific teachers
print("\n塚本先生's music assignments:")
music_conflicts = []
for day_idx, day in enumerate(days):
    for period in range(1, 7):
        classes = []
        for idx, row in schedule_df.iterrows():
            class_name = row.iloc[0] if pd.notna(row.iloc[0]) else ''
            if not class_name or class_name == '基本時間割' or not class_name.endswith('組'):
                continue
            col_idx = day_idx * 6 + period + 1
            if col_idx < len(row) and pd.notna(row.iloc[col_idx]) and row.iloc[col_idx] == '音':
                if '塚本' in teacher_map['音'][class_name]:
                    classes.append(class_name)
        if len(classes) > 1:
            print(f"  {day} P{period}: {', '.join(classes)}")
            music_conflicts.append((day, period, classes))

# Check 金子み先生's home economics
print("\n金子み先生's home economics assignments:")
home_ec_conflicts = []
for day_idx, day in enumerate(days):
    for period in range(1, 7):
        classes = []
        for idx, row in schedule_df.iterrows():
            class_name = row.iloc[0] if pd.notna(row.iloc[0]) else ''
            if not class_name or class_name == '基本時間割' or not class_name.endswith('組'):
                continue
            col_idx = day_idx * 6 + period + 1
            if col_idx < len(row) and pd.notna(row.iloc[col_idx]) and row.iloc[col_idx] == '家':
                if '金子み' in teacher_map['家'][class_name]:
                    classes.append(class_name)
        if len(classes) > 1:
            print(f"  {day} P{period}: {', '.join(classes)}")
            home_ec_conflicts.append((day, period, classes))

# Show which classes are Grade 5
print("\nGrade 5 classes in conflicts:")
if music_conflicts:
    print("Music conflicts with Grade 5:")
    for day, period, classes in music_conflicts:
        grade5_classes = [c for c in classes if '5組' in c]
        if grade5_classes:
            print(f"  {day} P{period}: Grade 5 classes = {', '.join(grade5_classes)}")

if home_ec_conflicts:
    print("Home Economics conflicts with Grade 5:")
    for day, period, classes in home_ec_conflicts:
        grade5_classes = [c for c in classes if '5組' in c]
        if grade5_classes:
            print(f"  {day} P{period}: Grade 5 classes = {', '.join(grade5_classes)}")