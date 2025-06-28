#!/usr/bin/env python3
"""5組のテスト期間中の配置を確認"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.infrastructure.config.path_config import path_config

def check_grade5_test_periods():
    """5組のテスト期間中の配置を確認"""
    
    # テスト期間
    test_periods = [
        ('月', '1'), ('月', '2'), ('月', '3'),
        ('火', '1'), ('火', '2'), ('火', '3'),
        ('水', '1'), ('水', '2')
    ]
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    print("=== 5組のテスト期間中の配置 ===\n")
    
    # 5組のクラス
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    
    # 各テスト期間について確認
    for day, period in test_periods:
        # 該当する列を見つける
        col_idx = None
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and p == period:
                col_idx = i + 1
                break
        
        if col_idx is None:
            continue
        
        print(f"{day}曜{period}校時:")
        
        # 通常学級のテスト科目を確認
        test_subjects = {}
        for row_idx in range(2, len(schedule_df)):
            row = schedule_df.iloc[row_idx]
            if pd.isna(row[0]) or row[0] == "":
                continue
            
            class_name = row[0]
            if '年' not in class_name or '組' not in class_name:
                continue
            
            # 学年を取得
            grade = int(class_name.split('年')[0])
            
            # 5組と6組、7組以外
            if '5組' not in class_name and '6組' not in class_name and '7組' not in class_name:
                subject = row[col_idx]
                if not pd.isna(subject):
                    if grade not in test_subjects:
                        test_subjects[grade] = subject
        
        # 5組の配置を確認
        violations = []
        for row_idx in range(2, len(schedule_df)):
            row = schedule_df.iloc[row_idx]
            class_name = row[0]
            
            if class_name in grade5_classes:
                subject = row[col_idx]
                grade = int(class_name.split('年')[0])
                
                # 同じ学年の通常学級のテスト科目と比較
                if grade in test_subjects and test_subjects[grade] == subject:
                    violations.append({
                        'class': class_name,
                        'subject': subject,
                        'test_subject': test_subjects[grade]
                    })
        
        # 結果を表示
        print(f"  通常学級のテスト: {test_subjects}")
        for grade5_class in grade5_classes:
            for row_idx in range(2, len(schedule_df)):
                row = schedule_df.iloc[row_idx]
                if row[0] == grade5_class:
                    subject = row[col_idx]
                    grade = int(grade5_class.split('年')[0])
                    status = "❌ 違反" if any(v['class'] == grade5_class for v in violations) else "✓ OK"
                    print(f"  {grade5_class}: {subject} {status}")
                    if status == "❌ 違反" and grade in test_subjects:
                        print(f"    → {grade}年生が{test_subjects[grade]}のテスト中、5組も{subject}は不適切")
        
        if violations:
            print(f"  ⚠️ 5組がテスト科目を配置している違反が{len(violations)}件")
        
        print()

if __name__ == "__main__":
    check_grade5_test_periods()