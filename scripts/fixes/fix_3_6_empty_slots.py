#!/usr/bin/env python3
"""
Fix empty slots in class 3-6 by syncing with parent class 3-3.
3-6 is an exchange class paired with 3-3, so non-jiritsu activities must match.
"""

import pandas as pd
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)


def main():
    """Fix empty slots in 3-6 by syncing with 3-3."""
    # Read the current schedule
    input_file = os.path.join(project_root, 'data', 'output', 'output_daily_fixed.csv')
    output_file = os.path.join(project_root, 'data', 'output', 'output_3_6_fixed.csv')
    
    print(f"Reading schedule from: {input_file}")
    
    # Read CSV
    df = pd.read_csv(input_file, header=None)
    
    # Extract time slot information from second row
    time_slots_row = df.iloc[1].tolist()[1:]  # Skip first column
    
    # Find the rows for 3-3 and 3-6
    class_3_3_idx = None
    class_3_6_idx = None
    
    for idx, row in df.iterrows():
        if row[0] == '3年3組':
            class_3_3_idx = idx
        elif row[0] == '3年6組':
            class_3_6_idx = idx
    
    if class_3_3_idx is None or class_3_6_idx is None:
        print("Error: Could not find 3年3組 or 3年6組 in the schedule")
        return
    
    print(f"Found 3年3組 at row {class_3_3_idx}")
    print(f"Found 3年6組 at row {class_3_6_idx}")
    
    # Get the subjects for both classes
    subjects_3_3 = df.iloc[class_3_3_idx].tolist()[1:]
    subjects_3_6 = df.iloc[class_3_6_idx].tolist()[1:]
    
    # Find empty slots in 3-6
    empty_slots = []
    fixes_made = []
    
    for i, (time_slot, subject_3_6, subject_3_3) in enumerate(zip(time_slots_row, subjects_3_6, subjects_3_3)):
        if pd.isna(subject_3_6) or subject_3_6 == '' or str(subject_3_6).strip() == '':
            # Parse day and period from column header
            day_info = df.iloc[0, i + 1]  # +1 because first column is class name
            period = time_slot
            
            empty_slots.append({
                'index': i,
                'day': day_info,
                'period': period,
                'parent_subject': subject_3_3,
                'column': i + 1  # Column index in DataFrame
            })
    
    print(f"\nFound {len(empty_slots)} empty slots in 3年6組:")
    for slot in empty_slots:
        print(f"  - {slot['day']} period {slot['period']}: Parent class (3-3) has '{slot['parent_subject']}'")
    
    # Check if 3-6 has jiritsu at these times
    print("\nChecking synchronization rules...")
    
    for slot in empty_slots:
        # Check if this is a jiritsu time for 3-6
        # During jiritsu, 3-6 can have different subjects than 3-3
        # Otherwise, they must match
        
        # For exchange classes, they should match parent class unless it's jiritsu time
        # Since these are empty slots, we should fill them with parent class subjects
        if slot['parent_subject'] and not pd.isna(slot['parent_subject']):
            print(f"\nFilling {slot['day']} period {slot['period']} with '{slot['parent_subject']}' (matching parent class)")
            df.iloc[class_3_6_idx, slot['column']] = slot['parent_subject']
            fixes_made.append({
                'day': slot['day'],
                'period': slot['period'],
                'subject': slot['parent_subject']
            })
    
    # Verify exchange class synchronization
    print("\n\nVerifying exchange class synchronization after fixes:")
    mismatches = []
    
    # Re-read the updated subjects
    subjects_3_3 = df.iloc[class_3_3_idx].tolist()[1:]
    subjects_3_6 = df.iloc[class_3_6_idx].tolist()[1:]
    
    for i, (time_slot, subject_3_6, subject_3_3) in enumerate(zip(time_slots_row, subjects_3_6, subjects_3_3)):
        if subject_3_6 and subject_3_3 and subject_3_6 != subject_3_3:
            # Check if 3-6 has jiritsu (自立) at this time
            if subject_3_6 != '自立':
                day_info = df.iloc[0, i + 1]
                period = time_slot
                mismatches.append({
                    'day': day_info,
                    'period': period,
                    '3-3': subject_3_3,
                    '3-6': subject_3_6
                })
    
    if mismatches:
        print(f"\nFound {len(mismatches)} synchronization mismatches (excluding jiritsu times):")
        for mismatch in mismatches:
            print(f"  - {mismatch['day']} period {mismatch['period']}: 3-3 has '{mismatch['3-3']}', 3-6 has '{mismatch['3-6']}'")
    else:
        print("✓ All non-jiritsu subjects are properly synchronized between 3-3 and 3-6")
    
    # Save the fixed schedule
    print(f"\nSaving fixed schedule to: {output_file}")
    df.to_csv(output_file, header=False, index=False)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary: Fixed {len(fixes_made)} empty slots in 3年6組")
    if fixes_made:
        print("\nFixes applied:")
        for fix in fixes_made:
            print(f"  - {fix['day']} period {fix['period']}: Added '{fix['subject']}'")
    
    print(f"\nFixed schedule saved to: {output_file}")


if __name__ == "__main__":
    main()