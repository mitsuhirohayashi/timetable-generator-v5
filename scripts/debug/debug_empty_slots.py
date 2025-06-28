#!/usr/bin/env python3
"""Debug why certain slots remain empty"""

import pandas as pd
from pathlib import Path

def analyze_empty_slots():
    # Read output file
    output_df = pd.read_csv('data/output/output.csv', encoding='utf-8')
    
    print("=== Empty Slots Analysis ===\n")
    
    # Days and periods mapping
    days = ['月', '火', '水', '木', '金']
    
    # Find empty slots
    empty_slots = []
    for idx, row in output_df.iterrows():
        # Skip header rows and empty rows
        if idx < 2:  # Skip header rows
            continue
            
        # Extract class info from first column (e.g., "1年1組")
        class_info = str(row.iloc[0])
        if pd.isna(row.iloc[0]) or not class_info or '年' not in class_info:
            continue
            
        # Parse grade and class number
        try:
            parts = class_info.split('年')
            grade = int(parts[0])
            class_num = int(parts[1].replace('組', ''))
        except (ValueError, IndexError):
            continue
            
        class_name = f"{grade}年{class_num}組"
        
        # Check each period
        for col_idx in range(2, len(row)):
            if pd.isna(row.iloc[col_idx]) or row.iloc[col_idx] == '':
                # Convert to day and period
                day_idx = (col_idx - 2) // 6
                period = ((col_idx - 2) % 6) + 1
                
                if day_idx < len(days):
                    empty_slots.append({
                        'class': class_name,
                        'grade': grade,
                        'class_num': class_num,
                        'day': days[day_idx],
                        'period': period,
                        'col_index': col_idx
                    })
    
    # Group by time slot
    from collections import defaultdict
    slots_by_time = defaultdict(list)
    
    for slot in empty_slots:
        key = f"{slot['day']}{slot['period']}"
        slots_by_time[key].append(slot['class'])
    
    print("Empty slots grouped by time:")
    for time_slot, classes in sorted(slots_by_time.items()):
        print(f"\n{time_slot}: {', '.join(classes)}")
        
    # Analyze 5組 specifically
    print("\n\n=== 5組 Analysis ===")
    grade5_empty = [s for s in empty_slots if s['class_num'] == 5]
    
    if grade5_empty:
        print(f"\nFound {len(grade5_empty)} empty slots in 5組 classes:")
        for slot in grade5_empty:
            print(f"  - {slot['class']} at {slot['day']}{slot['period']}")
    
    # Check if all 5組 have the same empty slot
    grade5_times = set()
    for slot in grade5_empty:
        grade5_times.add((slot['day'], slot['period']))
    
    if len(grade5_times) == 1:
        day, period = list(grade5_times)[0]
        print(f"\nAll 5組 classes have the same empty slot at {day}{period}")
        print("This suggests a synchronization issue or constraint preventing assignment.")
    
    # Check what's in the surrounding slots for 5組
    print("\n=== Checking surrounding assignments for 5組 ===")
    for idx, row in output_df.iterrows():
        if idx < 2:  # Skip headers
            continue
            
        class_info = str(row.iloc[0])
        if '5組' in class_info:
            print(f"\n{class_info}:")
            # Check Wednesday slots
            wed_start = 14  # Wednesday starts at column 14 (header + Mon 1-6 + Tue 1-6)
            for period in range(6):
                col_idx = wed_start + period
                value = row.iloc[col_idx] if col_idx < len(row) else None
                print(f"  水{period+1}: {value if value else '(empty)'}")

if __name__ == "__main__":
    analyze_empty_slots()