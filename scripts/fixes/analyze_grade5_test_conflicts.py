#!/usr/bin/env python3
"""
Analyze Grade 5 teacher conflicts during test periods more comprehensively.
"""

import pandas as pd
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def analyze_test_conflicts():
    """Analyze test period conflicts for Grade 5 classes"""
    
    print("=== Grade 5 Test Period Conflict Analysis ===\n")
    
    # Read the output schedule
    df = pd.read_csv('data/output/output.csv', header=None)
    
    # Set column names
    cols = ['Class'] + [f'{day}{period}' for day in ['月', '火', '水', '木', '金'] for period in range(1, 7)]
    df.columns = cols[:len(df.columns)]
    
    # Skip the header rows
    df = df[df['Class'].str.contains('組', na=False)]
    
    # Define test periods based on 技家 occurrences
    test_periods = []
    
    # Find all cells with 技家
    for col in df.columns[1:]:
        if df[col].str.contains('技家', na=False).any():
            # Get classes that have 技家 in this period
            test_classes = df[df[col] == '技家']['Class'].tolist()
            if test_classes:
                test_periods.append({
                    'period': col,
                    'classes': test_classes
                })
    
    print("Test periods found:")
    for tp in test_periods:
        print(f"\n{tp['period']}:")
        print(f"  Classes with 技家: {', '.join(tp['classes'])}")
        
    # Check what Grade 5 classes are doing during test periods
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    
    print("\n\nGrade 5 activities during test periods:")
    
    conflicts = []
    
    for tp in test_periods:
        period = tp['period']
        print(f"\n{period}:")
        
        # Check each grade level
        for grade in ['1年', '2年', '3年']:
            # Get test classes for this grade
            grade_test_classes = [c for c in tp['classes'] if c.startswith(grade)]
            
            if grade_test_classes:
                # Get Grade 5 class for this grade
                grade5_class = f"{grade}5組"
                
                if grade5_class in df['Class'].values:
                    grade5_subject = df[df['Class'] == grade5_class][period].iloc[0]
                    print(f"  {grade5_class}: {grade5_subject} (regular class)")
                    print(f"  Other {grade} classes: 技家 (test)")
                    
                    # This is a potential conflict
                    conflicts.append({
                        'period': period,
                        'grade5_class': grade5_class,
                        'grade5_subject': grade5_subject,
                        'test_classes': grade_test_classes
                    })
    
    # Read teacher mapping to check assignments
    teacher_df = pd.read_csv('data/config/teacher_subject_mapping.csv')
    
    print("\n\n=== Conflict Analysis ===")
    
    for conflict in conflicts:
        print(f"\nPeriod: {conflict['period']}")
        print(f"Grade 5 class: {conflict['grade5_class']} - {conflict['grade5_subject']}")
        
        # Find who teaches this subject to Grade 5
        grade = int(conflict['grade5_class'][0])
        grade5_teacher = teacher_df[
            (teacher_df['教科'] == conflict['grade5_subject']) &
            (teacher_df['学年'] == grade) &
            (teacher_df['組'] == 5)
        ]['教員名'].values
        
        if len(grade5_teacher) > 0:
            print(f"  Teacher for Grade 5: {grade5_teacher[0]}")
        
        # Check if same teacher is assigned to 技家
        test_teachers = teacher_df[
            (teacher_df['教科'] == '技家') &
            (teacher_df['学年'] == grade)
        ]['教員名'].unique()
        
        print(f"  Teachers for 技家 tests: {', '.join(test_teachers)}")
        
        # Check for conflicts
        if len(grade5_teacher) > 0 and grade5_teacher[0] in test_teachers:
            print(f"  ⚠️  CONFLICT: {grade5_teacher[0]} is assigned to both!")
    
    print("\n\n=== Summary ===")
    print(f"Total potential conflicts: {len(conflicts)}")
    
    # Specific check for 金子み
    kaneko_subjects = teacher_df[teacher_df['教員名'] == '金子み']['教科'].unique()
    print(f"\n金子み teaches: {', '.join(kaneko_subjects)}")
    
    # Check if 金子み is assigned to both Grade 5 regular classes and 技家
    if '技家' in kaneko_subjects:
        grade5_subjects = teacher_df[
            (teacher_df['教員名'] == '金子み') &
            (teacher_df['組'] == 5)
        ]['教科'].unique()
        
        non_grade5_subjects = teacher_df[
            (teacher_df['教員名'] == '金子み') &
            (teacher_df['組'] != 5) &
            (teacher_df['教科'] == '技家')
        ]
        
        if len(grade5_subjects) > 0 and len(non_grade5_subjects) > 0:
            print("\n⚠️  金子み is assigned to:")
            print(f"  - Grade 5 classes: {', '.join(grade5_subjects)}")
            print(f"  - Test supervision (技家) for: {non_grade5_subjects[['学年', '組']].values.tolist()}")
            print("\nThis creates a scheduling conflict during test periods!")
            
            print("\n📋 Recommendation:")
            print("Remove 金子み from 技家 assignments for non-Grade 5 classes")
            print("林 teacher can handle 技家 test supervision alone")


if __name__ == "__main__":
    analyze_test_conflicts()