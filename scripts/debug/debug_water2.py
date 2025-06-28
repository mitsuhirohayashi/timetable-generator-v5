#!/usr/bin/env python3
"""Debug water column 2 (水曜2限) test period violations."""

import pandas as pd
from pathlib import Path

def analyze_water2_violations():
    """Analyze water column 2 violations between input and output."""
    # Load CSVs
    input_path = Path("data/input/input.csv")
    output_path = Path("data/output/output.csv")
    
    input_df = pd.read_csv(input_path, header=[0, 1])
    output_df = pd.read_csv(output_path, header=[0, 1])
    
    print("=== Water Column 2 (水曜2限) Test Period Violation Analysis ===\n")
    
    # Water column 2 is the 14th column (index 13)
    # In input.csv it's labeled as ('水', '2')
    # In output.csv it's labeled as ('水.1', '2') due to duplicate column names
    
    water2_input_col = ('水', '2')
    # Check if output has duplicate column names
    water_cols = [col for col in output_df.columns if '水' in str(col[0]) and col[1] == '2']
    if water_cols:
        water2_output_col = water_cols[0]  # Use the first match
    else:
        water2_output_col = ('水', '2')  # Default to same as input
    
    print("Input.csv column names:")
    print([col for col in input_df.columns if '水' in str(col[0])])
    
    print("\nOutput.csv column names:")
    print([col for col in output_df.columns if '水' in str(col[0])])
    
    print("\n--- Water Column 2 Comparison ---")
    print(f"{'Class':<10} {'Input':<10} {'Output':<10} {'Status':<10}")
    print("-" * 40)
    
    violations = []
    
    for idx, class_name in enumerate(input_df.iloc[:, 0]):
        if pd.isna(class_name) or class_name == "":
            continue
            
        try:
            input_val = input_df.loc[idx, water2_input_col]
            output_val = output_df.loc[idx, water2_output_col]
            
            # Skip if either is NaN
            if pd.isna(input_val) or pd.isna(output_val):
                continue
                
            status = "✓" if input_val == output_val else "✗ CHANGED"
            print(f"{class_name:<10} {input_val:<10} {output_val:<10} {status:<10}")
            
            if input_val != output_val:
                violations.append({
                    'class': class_name,
                    'original': input_val,
                    'changed_to': output_val
                })
                
        except Exception as e:
            print(f"Error processing {class_name}: {e}")
    
    print("\n=== Summary of Violations ===")
    if violations:
        print(f"Found {len(violations)} violations in water column 2 (test period):")
        for v in violations:
            print(f"  - {v['class']}: {v['original']} → {v['changed_to']}")
        
        print("\nAccording to Follow-up.csv:")
        print("水曜日：１・２校時はテストなので時間割の変更をしないでください。")
        print("\nThese changes should NOT have been made during test period!")
    else:
        print("No violations found. All water column 2 subjects preserved correctly.")
    
    # Also check test period markers
    print("\n=== Checking for Test Period Markers ===")
    # Check if any "テスト" or "行" was placed
    test_markers = ['テスト', '行']
    for marker in test_markers:
        count = (output_df[water2_output_col] == marker).sum()
        if count > 0:
            print(f"Found {count} '{marker}' markers in water column 2")

if __name__ == "__main__":
    analyze_water2_violations()