#!/usr/bin/env python3
"""残りの空きスロットを埋めるスクリプト"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv
from collections import Counter

def find_empty_slots():
    """空きスロットを見つける"""
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    empty_slots = []
    
    # ヘッダー行を取得
    day_row = rows[0]
    period_row = rows[1]
    
    # 各クラスの空きスロットを確認
    for row_idx, row in enumerate(rows[2:], 2):
        if len(row) > 0 and row[0] and row[0] != "":
            class_name = row[0]
            
            # 特別なクラスはスキップ（6限目の欠、YTなど）
            for col_idx in range(1, len(row)):
                if col_idx < len(day_row) and col_idx < len(period_row):
                    day = day_row[col_idx]
                    period = period_row[col_idx]
                    
                    # 空きスロットを確認
                    if not row[col_idx] or row[col_idx] == "":
                        # 特別なスロットはスキップ
                        if should_skip_slot(class_name, day, period):
                            continue
                        
                        empty_slots.append({
                            'row': row_idx,
                            'col': col_idx,
                            'class': class_name,
                            'day': day,
                            'period': period
                        })
    
    return empty_slots

def should_skip_slot(class_name, day, period):
    """スキップすべきスロットかチェック"""
    # 3年生以外の6限目
    if period == "6" and "3年" not in class_name:
        return True
    
    # 3年生でも金曜6限はスキップ
    if "3年" in class_name and day == "金" and period == "6":
        return True
    
    return False

def get_class_subject_counts(class_name, rows):
    """特定クラスの科目数をカウント"""
    subjects = []
    for row in rows[2:]:
        if len(row) > 0 and row[0] == class_name:
            for cell in row[1:]:
                if cell and cell not in ["欠", "YT", ""]:
                    subjects.append(cell)
            break
    return Counter(subjects)

def get_class_base_hours(class_name):
    """特定クラスの標準時数を取得"""
    base_hours = {}
    with open("data/config/base_timetable.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から科目を取得
    subjects = [cell.strip() for cell in rows[1][1:] if cell.strip()]
    
    # 該当クラスの標準時数を取得
    for row in rows[2:]:
        if len(row) > 0 and row[0] == class_name:
            for i, subject in enumerate(subjects):
                if i + 1 < len(row) and row[i + 1]:
                    try:
                        hours = float(row[i + 1])
                        if hours > 0:
                            base_hours[subject] = hours
                    except ValueError:
                        pass
            break
    
    return base_hours

def find_best_subject_for_class(class_name, rows):
    """クラスに最適な科目を見つける"""
    current_counts = get_class_subject_counts(class_name, rows)
    base_hours = get_class_base_hours(class_name)
    
    # 固定科目を除外
    excluded = ["欠", "YT", "学", "学活", "道", "道徳", "総", "総合", "学総", "行", "行事"]
    
    # 主要教科を優先
    main_subjects = ["数", "国", "英", "理", "社", "算"]
    
    # 不足している主要教科を探す
    best_subject = None
    max_shortage = 0
    
    for subject in main_subjects:
        if subject in base_hours and subject not in excluded:
            current = current_counts.get(subject, 0)
            target = base_hours[subject]
            shortage = target - current
            if shortage > max_shortage:
                max_shortage = shortage
                best_subject = subject
    
    # 主要教科で不足がない場合は、他の教科を確認
    if not best_subject:
        for subject, target in base_hours.items():
            if subject not in excluded:
                current = current_counts.get(subject, 0)
                shortage = target - current
                if shortage > max_shortage:
                    max_shortage = shortage
                    best_subject = subject
    
    return best_subject

def fill_empty_slots():
    """空きスロットを埋める"""
    # output.csvを読み込む
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    empty_slots = find_empty_slots()
    
    print(f"=== 空きスロット数: {len(empty_slots)} ===")
    
    # 優先度の高い順にソート（3年6組の空きを優先）
    priority_slots = []
    other_slots = []
    
    for slot in empty_slots:
        if "3年6組" in slot['class']:
            priority_slots.append(slot)
        else:
            other_slots.append(slot)
    
    all_slots = priority_slots + other_slots
    
    # 各空きスロットを埋める
    filled_count = 0
    for slot in all_slots:
        subject = find_best_subject_for_class(slot['class'], rows)
        if subject:
            rows[slot['row']][slot['col']] = subject
            filled_count += 1
            print(f"{slot['class']} {slot['day']}曜{slot['period']}限 → {subject}")
    
    print(f"\n=== {filled_count}個の空きスロットを埋めました ===")
    
    if filled_count > 0:
        # ファイルに書き戻す
        with open("data/output/output.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print("data/output/output.csv を更新しました")
    
    # 残りの空きスロットを確認
    remaining = find_empty_slots()
    if remaining:
        print(f"\n=== 残り{len(remaining)}個の空きスロット ===")
        for slot in remaining[:10]:  # 最初の10個だけ表示
            print(f"{slot['class']} {slot['day']}曜{slot['period']}限")

if __name__ == "__main__":
    fill_empty_slots()