#!/usr/bin/env python3
"""
日内重複の詳細分析
"""
import csv
from pathlib import Path
from collections import defaultdict

def analyze_daily_duplicates():
    """日内重複を詳細に分析"""
    csv_path = Path("data/output/output.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]
    periods = rows[1][1:]
    
    # 固定科目（重複してもOKな科目）
    fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
    
    print("=== 日内重複の詳細分析 ===\n")
    
    all_duplicates = []
    
    # 各クラスについて分析
    for row_idx, row in enumerate(rows[2:], start=3):
        if not row[0] or not row[0].strip():
            continue
        
        class_name = row[0]
        schedule = row[1:]
        
        # 曜日ごとに科目をグループ化
        day_subjects = defaultdict(list)
        for i, (day, period, subject) in enumerate(zip(days, periods, schedule)):
            if subject and subject not in fixed_subjects:
                day_subjects[day].append((period, subject, i+1))  # i+1は列番号
        
        # 重複を検出
        class_duplicates = []
        for day, subjects in day_subjects.items():
            subject_count = defaultdict(list)
            for period, subject, col in subjects:
                subject_count[subject].append((period, col))
            
            for subject, occurrences in subject_count.items():
                if len(occurrences) > 1:
                    periods_str = ", ".join([f"{p}限" for p, _ in occurrences])
                    cols = [col for _, col in occurrences]
                    class_duplicates.append({
                        'class': class_name,
                        'row': row_idx,
                        'day': day,
                        'subject': subject,
                        'periods': periods_str,
                        'count': len(occurrences),
                        'columns': cols
                    })
        
        if class_duplicates:
            print(f"{class_name}（行{row_idx}）:")
            for dup in class_duplicates:
                print(f"  {dup['day']}曜日: {dup['subject']}が{dup['count']}回（{dup['periods']}）")
            print()
            all_duplicates.extend(class_duplicates)
    
    # 修正が原因と思われる重複を特定
    print("\n=== 私の修正が原因の重複 ===")
    recent_changes = [
        ("1年2組", "火", "5", "数"),  # 火曜5限を家→数
        ("2年2組", "月", "5", "英"),  # 月曜5限を音→英
        ("2年2組", "水", "3", "数"),  # 水曜3限を保→数
        ("3年3組", "月", "5", "国"),  # 月曜5限を保→国
        ("3年3組", "金", "2", "数"),  # 金曜2限を理→数
        ("2年5組", "木", "1", "数"),  # 木曜1限を作業→数
    ]
    
    for class_name, day, period, subject in recent_changes:
        # この変更が重複を引き起こしたか確認
        for dup in all_duplicates:
            if (dup['class'] == class_name and 
                dup['day'] == day and 
                dup['subject'] == subject and
                f"{period}限" in dup['periods']):
                print(f"{class_name}: {day}曜{period}限を{subject}に変更 → 重複発生")
    
    # 統計
    print(f"\n総重複数: {len(all_duplicates)}件")
    
    # クラス別重複数
    class_dup_count = defaultdict(int)
    for dup in all_duplicates:
        class_dup_count[dup['class']] += 1
    
    print("\nクラス別重複数:")
    for class_name, count in sorted(class_dup_count.items()):
        print(f"  {class_name}: {count}件")

if __name__ == "__main__":
    analyze_daily_duplicates()