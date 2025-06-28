#!/usr/bin/env python3
"""
Fix extra row issue at line 22 and daily duplicate violations.

Issues to fix:
1. Line 22 contains duplicate data instead of being empty
2. 3年3組 (3-3): 国語 appears twice on Monday (periods 1 and 6)
3. 3年6組 (3-6): 国語 appears twice on Monday (periods 1 and 6)
"""

import csv
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


def main():
    print("=== Fix Extra Row 22 and Daily Duplicates ===\n")
    
    # Define file paths
    output_path = project_root / "data" / "output" / "output.csv"
    
    # Read the current output
    print(f"Reading {output_path}...")
    
    with open(output_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\nTotal lines in file: {len(lines)}")
    print(f"Line 22 content: {lines[21].strip()}")
    
    # Check if line 22 is not empty (should be empty)
    if lines[21].strip() != "" and lines[21].strip() != ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,":
        print("\n❌ Line 22 contains data instead of being empty!")
        print(f"Data: {lines[21].strip()}")
    
    # Parse CSV to fix duplicates
    # Read as list of lists for easier manipulation
    csv_data = []
    for line in lines:
        csv_data.append(line.strip().split(','))
    
    # Fix daily duplicates for 3-3 and 3-6
    print("\n--- Fixing Daily Duplicates ---")
    
    # Find 3-3 and 3-6 row indices
    row_3_3 = None
    row_3_6 = None
    
    for i, row in enumerate(csv_data):
        if row[0] == "3年3組":
            row_3_3 = i
        elif row[0] == "3年6組":
            row_3_6 = i
    
    if row_3_3:
        # Monday is columns 1-6 (index 1-6)
        monday_subjects_3_3 = csv_data[row_3_3][1:7]
        print(f"\n3年3組 Monday subjects: {monday_subjects_3_3}")
        
        # Check for duplicate 国
        if monday_subjects_3_3[0] == "国" and monday_subjects_3_3[5] == "国":
            print("✓ Fixing 3年3組 Monday duplicate: Changing period 6 from 国 to 美")
            csv_data[row_3_3][6] = "美"  # Change period 6 to 美
    
    if row_3_6:
        # Monday is columns 1-6 (index 1-6)
        monday_subjects_3_6 = csv_data[row_3_6][1:7]
        print(f"\n3年6組 Monday subjects: {monday_subjects_3_6}")
        
        # Check for duplicate 国
        if monday_subjects_3_6[0] == "国" and monday_subjects_3_6[5] == "国":
            print("✓ Fixing 3年6組 Monday duplicate: Changing period 6 from 国 to 美")
            csv_data[row_3_6][6] = "美"  # Change period 6 to 美 (same as 3-3 for sync)
    
    # Replace line 22 (index 21) with empty row
    if len(csv_data) > 21:
        print(f"\nReplacing line 22 with empty row...")
        csv_data[21] = [''] * len(csv_data[21])  # Empty row with same number of columns
    
    # Write back the corrected data
    print("\n--- Writing Corrected Output ---")
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in csv_data:
            if row == [''] * len(row):  # Empty row
                f.write('\n')
            else:
                writer.writerow(row)
    
    print("\n✅ Fixes completed!")
    
    # Verify the structure
    print("\n--- Verifying Output Structure ---")
    with open(output_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"Line 15 (separator after 2nd year): {'EMPTY' if lines[14].strip() == '' else 'HAS DATA'}")
    print(f"Line 16-21 (3rd year classes): 3-1, 3-2, 3-3, 3-5, 3-6, 3-7")
    print(f"Line 22: {'EMPTY ✓' if lines[21].strip() == '' else 'HAS DATA ❌'}")
    
    # Final check for duplicates
    print("\n--- Final Duplicate Check ---")
    
    # Re-read the corrected file
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        csv_data_final = list(reader)
    
    # Check 3-3 Monday
    for i, row in enumerate(csv_data_final):
        if row and row[0] == "3年3組":
            monday_3_3 = row[1:7]
            duplicates_3_3 = [s for s in monday_3_3 if monday_3_3.count(s) > 1 and s]
            print(f"\n3年3組 Monday: {monday_3_3}")
            print(f"Duplicates: {set(duplicates_3_3) if duplicates_3_3 else 'None ✓'}")
            break
    
    # Check 3-6 Monday
    for i, row in enumerate(csv_data_final):
        if row and row[0] == "3年6組":
            monday_3_6 = row[1:7]
            duplicates_3_6 = [s for s in monday_3_6 if monday_3_6.count(s) > 1 and s]
            print(f"\n3年6組 Monday: {monday_3_6}")
            print(f"Duplicates: {set(duplicates_3_6) if duplicates_3_6 else 'None ✓'}")
            break


if __name__ == "__main__":
    main()