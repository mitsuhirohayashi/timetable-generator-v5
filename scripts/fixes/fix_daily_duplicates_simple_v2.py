#!/usr/bin/env python3
"""
Simple script to fix daily duplicates by replacing duplicate occurrences
"""

import csv
from collections import defaultdict
import random

def fix_daily_duplicates(input_file, output_file):
    """Fix daily duplicates in the schedule"""
    
    # Read the CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # Fixed subjects that should not be replaced
    fixed_subjects = {"欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家"}
    
    # Alternative subjects pool (prioritizing main subjects)
    main_subjects = ["数", "国", "英", "理", "社", "算"]
    other_subjects = ["音", "美", "技", "家", "保"]
    
    print("=== Fixing Daily Duplicates ===\n")
    
    # Process each class
    for row_idx, row in enumerate(rows[2:], start=2):
        if not row or not row[0]:
            continue
            
        class_name = row[0]
        changes_made = False
        
        # For each day
        for day_idx in range(5):  # 5 days
            day_subjects = defaultdict(list)
            
            # Count subjects for this day
            for period in range(6):
                col_idx = 1 + day_idx * 6 + period
                if col_idx < len(row) and row[col_idx]:
                    subject = row[col_idx].strip()
                    if subject and subject not in fixed_subjects:
                        day_subjects[subject].append((period, col_idx))
            
            # Find and fix duplicates
            for subject, occurrences in day_subjects.items():
                if len(occurrences) > 1:
                    # Keep the first occurrence, replace others
                    for i in range(1, len(occurrences)):
                        period, col_idx = occurrences[i]
                        
                        # Find subjects already used today
                        used_today = set()
                        for p in range(6):
                            c_idx = 1 + day_idx * 6 + p
                            if c_idx < len(row) and row[c_idx] and row[c_idx] not in fixed_subjects:
                                used_today.add(row[c_idx])
                        
                        # Find a replacement subject
                        replacement = None
                        
                        # Try main subjects first
                        for subj in main_subjects:
                            if subj not in used_today and subj != subject:
                                replacement = subj
                                break
                        
                        # If no main subject available, try others
                        if not replacement:
                            for subj in other_subjects:
                                if subj not in used_today and subj != subject:
                                    replacement = subj
                                    break
                        
                        # Make the replacement
                        if replacement:
                            old_value = row[col_idx]
                            row[col_idx] = replacement
                            changes_made = True
                            day_name = ["月", "火", "水", "木", "金"][day_idx]
                            print(f"{class_name} {day_name}曜{period+1}限: {old_value} → {replacement}")
    
    # Special handling for Grade 5 PE duplicates
    grade5_classes = ["1年5組", "2年5組", "3年5組"]
    grade5_rows = []
    
    for row_idx, row in enumerate(rows):
        if row and row[0] in grade5_classes:
            grade5_rows.append((row_idx, row))
    
    if grade5_rows:
        print("\n=== Fixing Grade 5 PE Duplicates (synchronized) ===")
        
        # For Monday (columns 1-6), keep PE in period 2, replace periods 3 and 5
        replacements = {
            3: "英",  # Period 3 -> English
            5: "算"   # Period 5 -> Math
        }
        
        for period, new_subject in replacements.items():
            col_idx = period  # Column index for Monday
            
            # Check if all Grade 5 classes have PE at this period
            all_have_pe = all(row[col_idx] == "保" for _, row in grade5_rows)
            
            if all_have_pe:
                # Replace for all Grade 5 classes
                for row_idx, row in grade5_rows:
                    rows[row_idx][col_idx] = new_subject
                    print(f"{row[0]} 月曜{period}限: 保 → {new_subject}")
    
    # Write the fixed schedule
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\nFixed schedule saved to: {output_file}")


def verify_fix(csv_file):
    """Verify that duplicates have been fixed"""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print("\n=== Verification ===")
    
    fixed_subjects = {"欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家"}
    remaining_duplicates = 0
    
    for row in rows[2:]:
        if not row or not row[0]:
            continue
            
        class_name = row[0]
        
        # Check each day
        for day_idx in range(5):
            day_subjects = defaultdict(int)
            
            for period in range(6):
                col_idx = 1 + day_idx * 6 + period
                if col_idx < len(row) and row[col_idx]:
                    subject = row[col_idx].strip()
                    if subject and subject not in fixed_subjects:
                        day_subjects[subject] += 1
            
            # Check for duplicates
            for subject, count in day_subjects.items():
                if count > 1:
                    day_name = ["月", "火", "水", "木", "金"][day_idx]
                    print(f"Remaining duplicate: {class_name} {day_name}曜日 - {subject} x{count}")
                    remaining_duplicates += 1
    
    if remaining_duplicates == 0:
        print("✓ All daily duplicates have been fixed!")
    else:
        print(f"\n⚠ {remaining_duplicates} duplicates remain")


if __name__ == "__main__":
    input_file = "data/output/output.csv"
    output_file = "data/output/output_fixed_duplicates.csv"
    
    fix_daily_duplicates(input_file, output_file)
    verify_fix(output_file)