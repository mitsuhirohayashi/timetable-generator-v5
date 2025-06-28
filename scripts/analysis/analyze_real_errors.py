#!/usr/bin/env python3
"""
D18×とD12×の真の原因を分析
保0はエラーではないことを前提に
"""
import csv
from pathlib import Path

def analyze_real_errors():
    """真のエラー原因を分析"""
    csv_path = Path("data/output/output.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print("=== D列のエラー分析（保0はエラーではない） ===")
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]
    periods = rows[1][1:]
    
    # 木曜日の列インデックスを特定
    thursday_indices = []
    for i, day in enumerate(days):
        if day == "木":
            thursday_indices.append(i + 1)  # +1はクラス名列のため
    
    print("\n木曜日の列インデックス:", thursday_indices)
    print("（D列は4列目なので、木曜1限に相当）")
    
    # D列（4列目）の内容を確認
    print("\n=== D列（4列目）の内容 ===")
    print("行 | クラス | D列の内容")
    print("-" * 30)
    
    for i, row in enumerate(rows[2:], start=3):
        if row[0] and row[0].strip() and i in [12, 13, 18, 19, 20]:
            if len(row) > 3:
                content = row[3]  # D列は4列目（0ベースで3）
                print(f"{i:2d} | {row[0]:8s} | {content}")
    
    # 別の可能性：日内重複のチェック
    print("\n=== 日内重複の可能性をチェック ===")
    
    class_schedules = {}
    for i, row in enumerate(rows[2:], start=3):
        if row[0] and row[0].strip():
            class_name = row[0]
            schedule = row[1:]
            class_schedules[class_name] = (schedule, i)
    
    # 各クラスの日内重複をチェック
    duplicates = []
    for class_name, (schedule, row_num) in class_schedules.items():
        if row_num not in [12, 18]:  # 問題の行に絞る
            continue
            
        # 各曜日ごとに重複をチェック
        day_subjects = {}
        for i, (day, period, subject) in enumerate(zip(days, periods, schedule)):
            if subject and subject not in ["欠", "YT", "道", "学", "総", "学総", "行"]:
                key = day
                if key not in day_subjects:
                    day_subjects[key] = []
                day_subjects[key].append((period, subject))
        
        # 重複を検出
        for day, subjects in day_subjects.items():
            subject_count = {}
            for period, subject in subjects:
                if subject not in subject_count:
                    subject_count[subject] = 0
                subject_count[subject] += 1
            
            for subject, count in subject_count.items():
                if count > 1:
                    duplicates.append({
                        'class': class_name,
                        'row': row_num,
                        'day': day,
                        'subject': subject,
                        'count': count
                    })
    
    if duplicates:
        print("\n日内重複が見つかりました:")
        for dup in duplicates:
            print(f"  行{dup['row']} {dup['class']}: {dup['day']}曜日に{dup['subject']}が{dup['count']}回")
    
    # 別の可能性：時数不足
    print("\n=== 時数の確認 ===")
    
    # 標準時数（仮）
    standard_hours = {
        "2年5組": {"数": 4, "英": 2, "国": 4, "理": 3, "社": 1},
        "3年3組": {"数": 4, "英": 4, "国": 3, "理": 4, "社": 4}
    }
    
    for class_name in ["2年5組", "3年3組"]:
        if class_name in class_schedules:
            schedule, row_num = class_schedules[class_name]
            subject_count = {}
            
            for subject in schedule:
                if subject and subject not in ["欠", "YT", "道", "学", "総", "学総", "行", "自立", "日生", "作業", "美", "音", "保", "技", "家", "技家"]:
                    if subject not in subject_count:
                        subject_count[subject] = 0
                    subject_count[subject] += 1
            
            print(f"\n{class_name}（行{row_num}）の主要教科時数:")
            if class_name in standard_hours:
                for subject, required in standard_hours[class_name].items():
                    actual = subject_count.get(subject, 0)
                    status = "OK" if actual >= required else "不足"
                    print(f"  {subject}: {actual}/{required} {status}")

if __name__ == "__main__":
    analyze_real_errors()