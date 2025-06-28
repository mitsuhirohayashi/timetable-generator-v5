#!/usr/bin/env python3
"""水曜2校時の詳細確認"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.infrastructure.config.path_config import path_config

def check_wednesday_2nd_detail():
    """水曜2校時の各クラスの授業と教師を確認"""
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行を確認
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 水曜2校時の列インデックスを特定
    target_col = None
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == '水' and period == '2':
            target_col = i + 1
            break
    
    print("=== 水曜2校時の詳細 ===\n")
    
    # 教師マッピングを読み込み
    teacher_mapping_df = pd.read_csv(path_config.config_dir / "teacher_subject_mapping.csv")
    teacher_subject_map = {}
    for _, row in teacher_mapping_df.iterrows():
        key = (row['学年'], row['組'], row['教科'])
        teacher_subject_map[key] = row['教員名']
    
    # 学年別に整理
    grade_data = {1: [], 2: [], 3: []}
    
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        parts = class_name.split('年')
        grade = int(parts[0])
        class_num = int(parts[1].replace('組', ''))
        subject = row[target_col]
        
        if not pd.isna(subject) and subject != "":
            # 教師を特定
            teacher_key = (grade, class_num, subject)
            teacher = teacher_subject_map.get(teacher_key, "不明")
            
            grade_data[grade].append({
                'class': class_name,
                'class_num': class_num,
                'subject': subject,
                'teacher': teacher
            })
    
    # 学年別に表示
    for grade in [1, 2, 3]:
        print(f"【{grade}年生】")
        for data in sorted(grade_data[grade], key=lambda x: x['class_num']):
            print(f"  {data['class']}: {data['subject']} ({data['teacher']}先生)")
        print()
    
    # 梶永先生の担当クラスを確認
    print("【梶永先生が担当するクラス】")
    kajinaga_classes = []
    for grade in [1, 2, 3]:
        for data in grade_data[grade]:
            if data['teacher'] == '梶永':
                kajinaga_classes.append(data['class'])
    
    if kajinaga_classes:
        print(f"  {', '.join(kajinaga_classes)}")
    else:
        print("  なし")
    
    print("\n【分析】")
    print("1年生: 1-1, 1-2, 1-3が数学 → テスト期間なので巡回監督で正常")
    print("5組: 各学年の5組の科目を確認")
    for grade in [1, 2, 3]:
        for data in grade_data[grade]:
            if data['class_num'] == 5:
                print(f"  {data['class']}: {data['subject']}")

if __name__ == "__main__":
    check_wednesday_2nd_detail()