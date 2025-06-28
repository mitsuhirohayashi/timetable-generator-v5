#!/usr/bin/env python3
"""
Fix music teacher conflicts by adding assistant teachers for simultaneous classes.
"""

import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def main():
    # Define paths
    teacher_mapping_path = project_root / 'data' / 'config' / 'teacher_subject_mapping.csv'
    
    print("=== Music Teacher Conflict Resolution ===")
    print("\nCurrent situation:")
    print("- 塚本先生 is teaching 3 classes simultaneously:")
    print("  - Monday P1: 3年1組, 3年2組, 3年3組")
    print("  - Tuesday P1: 1年1組, 1年2組, 1年3組")
    print("  - Wednesday P1: 2年1組, 2年2組, 2年3組")
    
    print("\n=== Proposed Solution ===")
    print("\nAdd assistant music teachers to help with simultaneous classes:")
    print("1. Keep 塚本先生 as the main music teacher")
    print("2. Add 渡部先生 as assistant music teacher for 1st grade")
    print("3. Add 中村先生 as assistant music teacher for 2nd grade")
    print("4. Add 斎藤先生 as assistant music teacher for 3rd grade")
    
    print("\nTeacher assignments after fix:")
    print("- 1年1組 音楽: 塚本 (main)")
    print("- 1年2組 音楽: 渡部 (assistant)")
    print("- 1年3組 音楽: 渡部 (assistant)")
    print("- 2年1組 音楽: 塚本 (main)")
    print("- 2年2組 音楽: 中村 (assistant)")
    print("- 2年3組 音楽: 中村 (assistant)")
    print("- 3年1組 音楽: 塚本 (main)")
    print("- 3年2組 音楽: 斎藤 (assistant)")
    print("- 3年3組 音楽: 斎藤 (assistant)")
    
    print("\nThis way:")
    print("- 塚本先生 only teaches 1 class at a time")
    print("- Assistant teachers handle the other simultaneous classes")
    print("- Music quality is maintained with proper staffing")
    
    # Prepare new entries
    new_entries = [
        # 渡部先生 - 1st grade assistant
        {'教員名': '渡部', '教科': '音', '学年': 1, '組': 2},
        {'教員名': '渡部', '教科': '音', '学年': 1, '組': 3},
        # 中村先生 - 2nd grade assistant  
        {'教員名': '中村', '教科': '音', '学年': 2, '組': 2},
        {'教員名': '中村', '教科': '音', '学年': 2, '組': 3},
        # 斎藤先生 - 3rd grade assistant
        {'教員名': '斎藤', '教科': '音', '学年': 3, '組': 2},
        {'教員名': '斎藤', '教科': '音', '学年': 3, '組': 3},
    ]
    
    # Entries to remove (we'll replace these with assistant teachers)
    remove_entries = [
        {'教員名': '塚本', '教科': '音', '学年': 1, '組': 2},
        {'教員名': '塚本', '教科': '音', '学年': 1, '組': 3},
        {'教員名': '塚本', '教科': '音', '学年': 2, '組': 2},
        {'教員名': '塚本', '教科': '音', '学年': 2, '組': 3},
        {'教員名': '塚本', '教科': '音', '学年': 3, '組': 2},
        {'教員名': '塚本', '教科': '音', '学年': 3, '組': 3},
    ]
    
    # Ask for confirmation
    print("\n" + "="*50)
    response = input("\nApply these changes to teacher_subject_mapping.csv? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        # Create backup
        backup_path = str(teacher_mapping_path).replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        df = pd.read_csv(teacher_mapping_path, encoding='utf-8-sig')
        df.to_csv(backup_path, index=False, encoding='utf-8-sig')
        print(f"\nCreated backup: {backup_path}")
        
        # Remove old entries
        for entry in remove_entries:
            mask = (
                (df['教員名'] == entry['教員名']) & 
                (df['教科'] == entry['教科']) & 
                (df['学年'] == entry['学年']) & 
                (df['組'] == entry['組'])
            )
            df = df[~mask]
            print(f"Removed: {entry['教員名']} from {entry['学年']}年{entry['組']}組 {entry['教科']}")
        
        # Add new entries
        new_df = pd.DataFrame(new_entries)
        df = pd.concat([df, new_df], ignore_index=True)
        for entry in new_entries:
            print(f"Added: {entry['教員名']} to {entry['学年']}年{entry['組']}組 {entry['教科']}")
        
        # Sort by teacher name, subject, grade, class
        df = df.sort_values(['教員名', '教科', '学年', '組'])
        
        # Save
        df.to_csv(teacher_mapping_path, index=False, encoding='utf-8-sig')
        print(f"\nUpdated teacher mapping saved to: {teacher_mapping_path}")
        
        print("\nNext steps:")
        print("1. Regenerate the schedule with: python3 main.py generate")
        print("2. Check for remaining conflicts")
    else:
        print("\nNo changes were made.")


if __name__ == "__main__":
    main()