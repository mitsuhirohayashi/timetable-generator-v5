#!/usr/bin/env python3
"""Trace how Monday empty slots are being filled."""

import pandas as pd
import re
from collections import defaultdict


def trace_monday_filling():
    """Trace the filling process for Monday."""
    
    # Read both CSVs
    input_df = pd.read_csv('data/input/input.csv', encoding='utf-8')
    output_df = pd.read_csv('data/output/output.csv', encoding='utf-8')
    
    print("Monday Empty Slot Filling Analysis")
    print("=" * 60)
    
    # Classes with duplicates on Monday
    duplicate_classes = [
        "1年2組", "1年3組", "1年5組", "1年6組", "1年7組",
        "2年1組", "2年2組", "2年3組", "2年5組", "2年7組", "3年5組"
    ]
    
    for class_name in duplicate_classes:
        # Find row index
        row_idx = None
        for idx in range(len(input_df)):
            if input_df.iloc[idx, 0] == class_name:
                row_idx = idx
                break
        
        if row_idx is None:
            continue
            
        print(f"\n{class_name}:")
        print("-" * 40)
        
        # Compare Monday slots (columns 1-6)
        changes = []
        monday_subjects_output = []
        
        for period in range(1, 7):
            col = period
            input_val = input_df.iloc[row_idx, col]
            output_val = output_df.iloc[row_idx, col]
            
            input_str = input_val if pd.notna(input_val) and input_val != '' else '<empty>'
            output_str = output_val if pd.notna(output_val) and output_val != '' else '<empty>'
            
            if pd.notna(output_val) and output_val != '':
                monday_subjects_output.append(output_val)
            
            if input_str != output_str:
                changes.append(f"  {period}限: {input_str} → {output_str}")
        
        # Show changes
        if changes:
            print("変更箇所:")
            for change in changes:
                print(change)
        
        # Count duplicates
        from collections import Counter
        counts = Counter(monday_subjects_output)
        duplicates = [(subj, count) for subj, count in counts.items() if count > 1]
        
        if duplicates:
            print("重複科目:")
            for subj, count in duplicates:
                print(f"  {subj}: {count}回")
                # Find which periods have this subject
                periods = []
                for period in range(1, 7):
                    if output_df.iloc[row_idx, period] == subj:
                        periods.append(f"{period}限")
                print(f"    配置場所: {', '.join(periods)}")
    
    # Analyze pattern
    print("\n\n=== パターン分析 ===")
    print("空きスロットを埋める際に、既存の科目が考慮されていない可能性があります。")
    
    # Check if it's always the same subjects being duplicated
    all_duplicates = defaultdict(int)
    for class_name in duplicate_classes:
        row_idx = None
        for idx in range(len(output_df)):
            if output_df.iloc[idx, 0] == class_name:
                row_idx = idx
                break
        
        if row_idx is None:
            continue
        
        monday_subjects = []
        for period in range(1, 7):
            val = output_df.iloc[row_idx, period]
            if pd.notna(val) and val != '':
                monday_subjects.append(val)
        
        counts = Counter(monday_subjects)
        for subj, count in counts.items():
            if count > 1:
                all_duplicates[subj] += 1
    
    print("\n重複している科目の頻度:")
    for subj, freq in sorted(all_duplicates.items(), key=lambda x: x[1], reverse=True):
        print(f"  {subj}: {freq}クラスで重複")


if __name__ == '__main__':
    trace_monday_filling()