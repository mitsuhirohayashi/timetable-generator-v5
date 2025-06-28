#!/usr/bin/env python3
"""空きスロットの分析スクリプト"""

import pandas as pd
import os
from pathlib import Path

def analyze_empty_slots():
    """空きスロットを分析"""
    
    # CSVファイルを読み込み
    output_path = Path("data/output/output.csv")
    followup_path = Path("data/input/Follow-up.csv")
    
    # output.csvを読み込み
    df = pd.read_csv(output_path, header=None)
    
    # ヘッダー行を抽出
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # データ部分を抽出（3行目以降）
    data_df = df.iloc[2:, :]
    
    # 空きスロットを検出
    empty_slots = []
    
    for idx, row in data_df.iterrows():
        if pd.isna(row.iloc[0]) or row.iloc[0] == "":
            continue
            
        class_name = row.iloc[0]
        
        for col_idx in range(1, len(row)):
            if pd.isna(row.iloc[col_idx]) or row.iloc[col_idx] == "":
                day = days[col_idx-1]
                period = periods[col_idx-1]
                empty_slots.append({
                    'class': class_name,
                    'day': day,
                    'period': period,
                    'slot': f"{day}{period}限"
                })
    
    # Follow-up.csvから教師不在情報を抽出
    teacher_absences = {}
    
    with open(followup_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    current_day = None
    for line in lines:
        line = line.strip()
        if '曜日：' in line:
            current_day = line.split('曜日')[0]
        elif current_day and ('不在' in line or '年休' in line or '研修' in line or '振休' in line):
            if current_day not in teacher_absences:
                teacher_absences[current_day] = []
            teacher_absences[current_day].append(line)
    
    # 結果を表示
    print("=== 空きスロットの分析結果 ===\n")
    print(f"総空きスロット数: {len(empty_slots)}\n")
    
    # 曜日・時限別に集計
    by_day_period = {}
    for slot in empty_slots:
        key = f"{slot['day']}{slot['period']}限"
        if key not in by_day_period:
            by_day_period[key] = []
        by_day_period[key].append(slot['class'])
    
    print("曜日・時限別の空きスロット:")
    for key, classes in sorted(by_day_period.items()):
        print(f"\n{key}: {len(classes)}クラス")
        for cls in sorted(classes):
            print(f"  - {cls}")
    
    # 教師不在との関連を分析
    print("\n\n=== 教師不在情報との関連 ===")
    
    # 月曜日の空きスロット
    mon_empty = [s for s in empty_slots if s['day'] == '月']
    if mon_empty and '月' in teacher_absences:
        print("\n月曜日:")
        print("教師不在情報:")
        for absence in teacher_absences['月']:
            print(f"  - {absence}")
        print(f"空きスロット数: {len(mon_empty)}")
    
    # 火曜日の空きスロット
    tue_empty = [s for s in empty_slots if s['day'] == '火']
    if tue_empty and '火' in teacher_absences:
        print("\n火曜日:")
        print("教師不在情報:")
        for absence in teacher_absences['火']:
            print(f"  - {absence}")
        print(f"空きスロット数: {len(tue_empty)}")
    
    # 水曜日の空きスロット
    wed_empty = [s for s in empty_slots if s['day'] == '水']
    if wed_empty and '水' in teacher_absences:
        print("\n水曜日:")
        print("教師不在情報:")
        for absence in teacher_absences['水']:
            print(f"  - {absence}")
        print(f"空きスロット数: {len(wed_empty)}")
    
    # クラス別に集計
    print("\n\n=== クラス別の空きスロット数 ===")
    by_class = {}
    for slot in empty_slots:
        cls = slot['class']
        if cls not in by_class:
            by_class[cls] = 0
        by_class[cls] += 1
    
    for cls, count in sorted(by_class.items(), key=lambda x: x[1], reverse=True):
        print(f"{cls}: {count}スロット")
    
    # 特に多い空きスロットのパターンを分析
    print("\n\n=== 特に多い空きスロットのパターン ===")
    
    # 5組の水曜4限
    grade5_wed4 = [s for s in empty_slots if '5組' in s['class'] and s['day'] == '水' and s['period'] == '4']
    if grade5_wed4:
        print(f"\n5組の水曜4限: {len(grade5_wed4)}クラス")
        print("→ 5組は合同授業のため、全クラス同時に埋める必要があります")
    
    # 3年生の6限
    grade3_6th = [s for s in empty_slots if '3年' in s['class'] and s['period'] == '6']
    if grade3_6th:
        print(f"\n3年生の6限: {len(grade3_6th)}スロット")
        print("→ 3年生は月火水の6限も授業可能です")

if __name__ == "__main__":
    analyze_empty_slots()