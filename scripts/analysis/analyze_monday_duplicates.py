#!/usr/bin/env python3
"""
Analyze Monday daily duplicates in detail
"""

import csv
from collections import defaultdict

def analyze_monday_duplicates(csv_file):
    """Analyze daily duplicates for Monday"""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # Extract headers
    days = rows[0][1:]  # Skip first column
    periods = rows[1][1:]  # Skip first column
    
    print("=== Monday Daily Duplicate Analysis ===\n")
    
    # For each class
    for row in rows[2:]:
        if not row or not row[0]:
            continue
            
        class_name = row[0]
        
        # Count subjects for Monday (first 6 columns after class name)
        monday_subjects = defaultdict(list)
        
        for i in range(1, 7):  # Monday periods 1-6
            if i < len(row) and row[i]:
                subject = row[i].strip()
                if subject:
                    monday_subjects[subject].append(i)
        
        # Find duplicates
        duplicates = [(subj, periods) for subj, periods in monday_subjects.items() if len(periods) > 1]
        
        if duplicates:
            print(f"{class_name}:")
            for subject, periods in duplicates:
                print(f"  - {subject} appears {len(periods)} times (periods: {periods})")
            print()
    
    # Special analysis for Grade 5
    print("\n=== Grade 5 Monday Schedule ===")
    grade5_classes = ["1年5組", "2年5組", "3年5組"]
    
    for row in rows[2:]:
        if row and row[0] in grade5_classes:
            class_name = row[0]
            monday_schedule = row[1:7] if len(row) > 6 else row[1:]
            print(f"{class_name}: {monday_schedule}")
    
    # Count total PE for Grade 5 on Monday
    print("\n=== Grade 5 PE Count on Monday ===")
    for row in rows[2:]:
        if row and row[0] in grade5_classes:
            class_name = row[0]
            pe_count = sum(1 for i in range(1, 7) if i < len(row) and row[i] == "保")
            print(f"{class_name}: {pe_count} PE classes")


def analyze_all_days_duplicates(csv_file):
    """Analyze daily duplicates for all days"""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print("\n\n=== All Days Daily Duplicate Analysis ===\n")
    
    days_map = {
        0: "月", 1: "火", 2: "水", 3: "木", 4: "金"
    }
    
    total_duplicates = 0
    
    # For each class
    for row in rows[2:]:
        if not row or not row[0]:
            continue
            
        class_name = row[0]
        class_duplicates = []
        
        # For each day
        for day_idx in range(5):  # 5 days
            day_subjects = defaultdict(list)
            
            # Count subjects for this day (6 periods per day)
            for period in range(6):
                col_idx = 1 + day_idx * 6 + period
                if col_idx < len(row) and row[col_idx]:
                    subject = row[col_idx].strip()
                    if subject and subject not in ["欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家"]:
                        day_subjects[subject].append(period + 1)
            
            # Find duplicates for this day
            for subject, periods in day_subjects.items():
                if len(periods) > 1:
                    class_duplicates.append((days_map[day_idx], subject, periods))
                    total_duplicates += 1
        
        if class_duplicates:
            print(f"{class_name}:")
            for day, subject, periods in class_duplicates:
                print(f"  - {day}曜日: {subject} x{len(periods)} (periods: {periods})")
            print()
    
    print(f"\nTotal duplicate violations: {total_duplicates}")


if __name__ == "__main__":
    csv_file = "data/output/output.csv"
    
    analyze_monday_duplicates(csv_file)
    analyze_all_days_duplicates(csv_file)