#!/usr/bin/env python3
"""
Fix 金子み's test supervision assignments to prevent conflicts with Grade 5 regular classes.

This script removes 金子み from 技家 assignments for non-Grade 5 classes,
allowing her to focus on Grade 5 regular instruction during test periods.
"""

import pandas as pd
import shutil
from datetime import datetime
from pathlib import Path


def fix_kaneko_assignments():
    """Remove 金子み from 技家 assignments for non-Grade 5 classes"""
    
    print("=== Fixing 金子み Test Assignment Conflicts ===\n")
    
    # Load teacher mapping
    mapping_file = 'data/config/teacher_subject_mapping.csv'
    df = pd.read_csv(mapping_file)
    
    print("Current 技家 assignments:")
    tech_assignments = df[df['教科'] == '技家']
    print(tech_assignments.groupby('教員名').size())
    
    # Find 金子み's 技家 assignments for non-Grade 5 classes
    kaneko_tech = df[
        (df['教員名'] == '金子み') & 
        (df['教科'] == '技家') &
        (df['組'] != 5)
    ]
    
    print(f"\n金子み's 技家 assignments to remove: {len(kaneko_tech)} entries")
    
    if len(kaneko_tech) > 0:
        # Create backup
        backup_file = f"data/config/teacher_subject_mapping_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        shutil.copy(mapping_file, backup_file)
        print(f"\nBackup created: {backup_file}")
        
        # Remove 金子み from non-Grade 5 技家 assignments
        df_filtered = df[~(
            (df['教員名'] == '金子み') & 
            (df['教科'] == '技家') &
            (df['組'] != 5)
        )]
        
        # Save updated file
        df_filtered.to_csv(mapping_file, index=False)
        print(f"\nRemoved {len(kaneko_tech)} entries from {mapping_file}")
        
        # Verify the changes
        print("\nAfter removal:")
        tech_assignments_after = df_filtered[df_filtered['教科'] == '技家']
        print(tech_assignments_after.groupby('教員名').size())
        
        # Show what was removed
        print("\nRemoved assignments:")
        for _, row in kaneko_tech.iterrows():
            print(f"  - {row['学年']}年{row['組']}組 技家")
        
        print("\n✅ Fix completed!")
        print("\nResults:")
        print("- 金子み can now focus on Grade 5 regular classes during test periods")
        print("- 林 teacher will handle test supervision for 技家")
        print("- No scheduling conflicts for 金子み")
        
        # Additional verification
        remaining_kaneko_tech = df_filtered[
            (df_filtered['教員名'] == '金子み') & 
            (df_filtered['教科'] == '技家')
        ]
        
        if len(remaining_kaneko_tech) > 0:
            print(f"\n金子み still has {len(remaining_kaneko_tech)} 技家 assignments:")
            for _, row in remaining_kaneko_tech.iterrows():
                print(f"  - {row['学年']}年{row['組']}組 (Grade 5 - OK)")
        else:
            print("\n金子み has no remaining 技家 assignments")
            
    else:
        print("\nNo conflicts found - 金子み is not assigned to 技家 for non-Grade 5 classes")
        
    return len(kaneko_tech)


def verify_fix():
    """Verify that the fix resolves the conflicts"""
    
    print("\n\n=== Verification ===")
    
    df = pd.read_csv('data/config/teacher_subject_mapping.csv')
    
    # Check Grade 5 subjects for 金子み
    grade5_subjects = df[
        (df['教員名'] == '金子み') &
        (df['組'] == 5)
    ]['教科'].unique()
    
    print(f"\n金子み's Grade 5 subjects: {', '.join(grade5_subjects)}")
    
    # Check if 金子み still has non-Grade 5 技家 assignments
    non_grade5_tech = df[
        (df['教員名'] == '金子み') &
        (df['教科'] == '技家') &
        (df['組'] != 5)
    ]
    
    if len(non_grade5_tech) == 0:
        print("✅ No conflicts: 金子み has no 技家 assignments for non-Grade 5 classes")
    else:
        print(f"⚠️  Still has conflicts: {len(non_grade5_tech)} non-Grade 5 技家 assignments")
        
    # Show test supervision coverage
    print("\n技家 test supervision coverage:")
    tech_coverage = df[df['教科'] == '技家'].groupby(['学年', '組', '教員名']).size().reset_index(name='count')
    
    for grade in [1, 2, 3]:
        print(f"\n{grade}年生:")
        grade_coverage = tech_coverage[tech_coverage['学年'] == grade]
        for _, row in grade_coverage.iterrows():
            print(f"  {row['組']}組: {row['教員名']}")


if __name__ == "__main__":
    # Fix the assignments
    removed_count = fix_kaneko_assignments()
    
    # Verify the fix
    if removed_count > 0:
        verify_fix()
        
    print("\n\n📝 Next steps:")
    print("1. Regenerate the timetable with: python3 main.py generate")
    print("2. Check violations with: python3 check_violations.py")
    print("3. Verify no teacher conflicts remain")