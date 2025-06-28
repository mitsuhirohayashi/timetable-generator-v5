#!/usr/bin/env python3
"""5組の水曜4限を簡単に埋めるスクリプト"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv
from collections import Counter

def get_subject_counts():
    """5組の現在の科目数をカウント"""
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # 5組の科目をカウント
    subjects = []
    for row in rows[2:]:
        if len(row) > 0 and "5組" in row[0]:
            for i in range(1, len(row)):
                if row[i] and row[i] not in ["欠", "YT", "空き", ""]:
                    subjects.append(row[i])
    
    return Counter(subjects)

def get_base_hours():
    """5組の標準時数を取得"""
    base_hours = {}
    with open("data/config/base_timetable.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から科目を取得
    subjects = [cell.strip() for cell in rows[1][1:] if cell.strip()]
    
    # 5組の標準時数を取得
    for row in rows[2:]:
        if len(row) > 0 and "5組" in row[0]:
            for i, subject in enumerate(subjects):
                if i + 1 < len(row) and row[i + 1]:
                    try:
                        hours = float(row[i + 1])
                        if hours > 0:
                            base_hours[subject] = base_hours.get(subject, 0) + hours
                    except ValueError:
                        pass
    
    return base_hours

def find_best_subject():
    """5組の水曜4限に配置する最適な科目を見つける"""
    current_counts = get_subject_counts()
    base_hours = get_base_hours()
    
    print("=== 現在の配置数 ===")
    for subject, count in sorted(current_counts.items()):
        print(f"{subject}: {count}回")
    
    print("\n=== 標準時数（3クラス合計） ===")
    for subject, hours in sorted(base_hours.items(), key=lambda x: x[1], reverse=True):
        print(f"{subject}: {hours}時間")
    
    # 主要教科を優先
    main_subjects = ["数", "国", "英", "理", "社", "算"]
    
    # 不足している主要教科を探す
    best_subject = None
    max_shortage = 0
    
    for subject in main_subjects:
        if subject in base_hours:
            current = current_counts.get(subject, 0)
            target = base_hours[subject]
            shortage = target - current
            print(f"\n{subject}: 標準{target} - 現在{current} = 不足{shortage}")
            if shortage > max_shortage:
                max_shortage = shortage
                best_subject = subject
    
    # 主要教科で不足がない場合は、他の教科を確認
    if not best_subject:
        for subject, target in base_hours.items():
            if subject not in ["欠", "YT", "学", "学活", "道", "道徳", "総", "総合", "学総"]:
                current = current_counts.get(subject, 0)
                shortage = target - current
                if shortage > max_shortage:
                    max_shortage = shortage
                    best_subject = subject
    
    return best_subject

def fill_wed4():
    """水曜4限を埋める"""
    best_subject = find_best_subject()
    
    if not best_subject:
        print("\n適切な科目が見つかりません")
        return
    
    print(f"\n=== 水曜4限に「{best_subject}」を配置します ===")
    
    # output.csvを読み込む
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # 水曜4限の列を見つける
    day_row = rows[0]
    period_row = rows[1]
    wed4_col = None
    for i, (day, period) in enumerate(zip(day_row, period_row)):
        if day == "水" and period == "4":
            wed4_col = i
            break
    
    if wed4_col is None:
        print("水曜4限が見つかりません")
        return
    
    # 5組の行を更新
    updated = False
    for i, row in enumerate(rows[2:], 2):
        if len(row) > 0 and "5組" in row[0]:
            if wed4_col < len(row):
                if not row[wed4_col] or row[wed4_col] == "":
                    row[wed4_col] = best_subject
                    updated = True
                    print(f"{row[0]}の水曜4限を「{best_subject}」に更新")
            else:
                # 列が足りない場合は拡張
                while len(row) <= wed4_col:
                    row.append("")
                row[wed4_col] = best_subject
                updated = True
                print(f"{row[0]}の水曜4限を「{best_subject}」に更新")
    
    if updated:
        # ファイルに書き戻す
        with open("data/output/output.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print("\ndata/output/output.csv を更新しました")
    else:
        print("\n更新する5組が見つかりませんでした")

if __name__ == "__main__":
    fill_wed4()