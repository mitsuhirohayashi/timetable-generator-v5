#!/usr/bin/env python3
"""体育館使用違反の詳細分析"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

def analyze_gym_violations():
    """体育館使用違反を詳細に分析"""
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行をスキップして処理
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 時間ごとの体育授業を収集
    time_pe_classes = defaultdict(list)
    
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        for col_idx in range(1, len(row)):
            subject = row[col_idx]
            if pd.isna(subject) or subject == "":
                continue
                
            # 体育関連科目かチェック
            if subject in ['保', '保健', '体育', '保健体育']:
                day_idx = (col_idx - 1) // 6
                period_idx = (col_idx - 1) % 6
                day = days[col_idx - 1]
                period = periods[col_idx - 1]
                
                time_key = (day, period)
                time_pe_classes[time_key].append(class_name)
    
    print("=== 体育館使用違反の詳細分析 ===\n")
    
    violations = []
    
    for (day, period), classes in time_pe_classes.items():
        if len(classes) > 1:
            # 5組の合同体育かチェック
            is_grade5_joint = all('5組' in c for c in classes)
            
            violations.append({
                'day': day,
                'period': period,
                'classes': classes,
                'count': len(classes),
                'is_grade5_joint': is_grade5_joint
            })
    
    # 違反を表示
    real_violations = [v for v in violations if not v['is_grade5_joint']]
    grade5_joints = [v for v in violations if v['is_grade5_joint']]
    
    print(f"体育館使用重複: {len(violations)} 件")
    print(f"- 5組合同体育: {len(grade5_joints)} 件（正常）")
    print(f"- 実際の違反: {len(real_violations)} 件\n")
    
    if grade5_joints:
        print("【5組合同体育】")
        for v in grade5_joints:
            print(f"  {v['day']}{v['period']}校時: {', '.join(v['classes'])}")
        print()
    
    if real_violations:
        print("【体育館使用違反】")
        for v in sorted(real_violations, key=lambda x: x['count'], reverse=True):
            print(f"  {v['day']}{v['period']}校時: {v['count']}クラスが同時使用")
            print(f"    クラス: {', '.join(v['classes'])}")
        print()
        
        # 曜日別統計
        day_counts = defaultdict(int)
        for v in real_violations:
            day_counts[v['day']] += 1
        
        print("曜日別違反件数:")
        for day, count in sorted(day_counts.items()):
            print(f"  {day}曜日: {count} 件")

if __name__ == "__main__":
    analyze_gym_violations()