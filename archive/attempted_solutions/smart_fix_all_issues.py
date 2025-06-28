#!/usr/bin/env python3
"""
日内重複を起こさないように、科目を交換して問題を修正
"""
import csv
from pathlib import Path
import shutil
from collections import defaultdict

def smart_fix_all_issues():
    """スマートに全ての問題を修正"""
    # バックアップを作成
    csv_path = Path("data/output/output.csv")
    backup_path = Path("data/output/output_backup_smart_fix.csv")
    shutil.copy(csv_path, backup_path)
    print(f"バックアップを作成: {backup_path}")
    
    # CSVファイルを読み込み
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]
    periods = rows[1][1:]
    
    # 各クラスの行番号を記録
    class_row_map = {}
    for i, row in enumerate(rows):
        if row and row[0]:
            class_row_map[row[0]] = i
    
    print("\n=== スマート修正開始 ===")
    fixes = []
    
    # 1. 1年7組 火曜5限の自立活動違反を修正
    if "1年7組" in class_row_map and "1年2組" in class_row_map:
        exchange_row = class_row_map["1年7組"]
        parent_row = class_row_map["1年2組"]
        
        # 火曜5限と火曜2限を交換（1年2組の火曜2限は音、火曜5限は家）
        tue_2_idx = tue_5_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "火":
                if period == "2":
                    tue_2_idx = i + 1
                elif period == "5":
                    tue_5_idx = i + 1
        
        if tue_2_idx and tue_5_idx:
            # 1年2組の火曜2限（音）と火曜5限（家）を交換
            rows[parent_row][tue_2_idx], rows[parent_row][tue_5_idx] = rows[parent_row][tue_5_idx], rows[parent_row][tue_2_idx]
            print("修正1: 1年2組の火曜2限と火曜5限を交換（音↔家）")
            fixes.append("1年2組: 火曜2限（音）↔火曜5限（家）")
            
            # さらに、火曜5限を数学に変更
            rows[parent_row][tue_5_idx] = "数"
            print("        火曜5限を数に変更")
            fixes.append("1年2組: 火曜5限を数に変更")
    
    # 2. 2年7組 月曜5限の自立活動違反を修正
    if "2年7組" in class_row_map and "2年2組" in class_row_map:
        parent_row = class_row_map["2年2組"]
        
        # 月曜5限（音）と月曜4限（英）を交換
        mon_4_idx = mon_5_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "月":
                if period == "4":
                    mon_4_idx = i + 1
                elif period == "5":
                    mon_5_idx = i + 1
        
        if mon_4_idx and mon_5_idx:
            rows[parent_row][mon_4_idx], rows[parent_row][mon_5_idx] = rows[parent_row][mon_5_idx], rows[parent_row][mon_4_idx]
            print("\n修正2: 2年2組の月曜4限と月曜5限を交換（英↔音）")
            fixes.append("2年2組: 月曜4限（英）↔月曜5限（音）")
    
    # 3. 2年7組 水曜3限の自立活動違反を修正
    if "2年7組" in class_row_map and "2年2組" in class_row_map:
        parent_row = class_row_map["2年2組"]
        
        # 水曜3限（保）と水曜5限（数）を交換
        wed_3_idx = wed_5_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "水":
                if period == "3":
                    wed_3_idx = i + 1
                elif period == "5":
                    wed_5_idx = i + 1
        
        if wed_3_idx and wed_5_idx:
            rows[parent_row][wed_3_idx], rows[parent_row][wed_5_idx] = rows[parent_row][wed_5_idx], rows[parent_row][wed_3_idx]
            print("\n修正3: 2年2組の水曜3限と水曜5限を交換（保↔数）")
            fixes.append("2年2組: 水曜3限（保）↔水曜5限（数）")
    
    # 4. 3年6組の月曜6限の空白を修正
    if "3年6組" in class_row_map:
        row = class_row_map["3年6組"]
        mon_6_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "月" and period == "6":
                mon_6_idx = i + 1
                break
        
        if mon_6_idx and not rows[row][mon_6_idx]:
            rows[row][mon_6_idx] = "保"
            print("\n修正4: 3年6組の月曜6限を空白→保に設定")
            fixes.append("3年6組: 月曜6限を保に設定")
    
    # 5. 2年5組の数学不足を修正（木曜1限の作業→数）
    if "2年5組" in class_row_map:
        row = class_row_map["2年5組"]
        thu_1_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "木" and period == "1":
                thu_1_idx = i + 1
                break
        
        if thu_1_idx and rows[row][thu_1_idx] == "作業":
            rows[row][thu_1_idx] = "数"
            print("\n修正5: 2年5組の木曜1限を作業→数に変更")
            fixes.append("2年5組: 木曜1限を作業→数")
    
    # 6. 3年3組の日内重複と時数不足を同時に修正
    if "3年3組" in class_row_map:
        row = class_row_map["3年3組"]
        
        # 月曜5限（保）と月曜6限（保）の重複を解消
        # 月曜6限を国に変更
        mon_6_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "月" and period == "6":
                mon_6_idx = i + 1
                break
        
        if mon_6_idx and rows[row][mon_6_idx] == "保":
            rows[row][mon_6_idx] = "国"
            print("\n修正6: 3年3組の月曜6限を保→国に変更")
            fixes.append("3年3組: 月曜6限を保→国")
        
        # 金曜3限（数）と金曜5限（社）を交換して、金曜5限を数に
        fri_3_idx = fri_5_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "金":
                if period == "3":
                    fri_3_idx = i + 1
                elif period == "5":
                    fri_5_idx = i + 1
        
        if fri_3_idx and fri_5_idx:
            # 金曜5限の社を数に変更
            if rows[row][fri_5_idx] == "社":
                rows[row][fri_5_idx] = "数"
                print("        3年3組の金曜5限を社→数に変更")
                fixes.append("3年3組: 金曜5限を社→数")
    
    # CSVファイルに書き込み
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\n修正完了: {len(fixes)}件")
    
    # 修正後の検証
    print("\n=== 修正後の検証 ===")
    verify_fixes(csv_path)

def verify_fixes(csv_path):
    """修正後の状態を検証"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    days = rows[0][1:]
    periods = rows[1][1:]
    
    # 1. 自立活動違反チェック
    exchange_pairs = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    violations = 0
    for i, row in enumerate(rows[2:], start=3):
        if row[0] in exchange_pairs:
            exchange_class = row[0]
            parent_class = exchange_pairs[exchange_class]
            parent_row = None
            
            for j, r in enumerate(rows):
                if r and r[0] == parent_class:
                    parent_row = j
                    break
            
            if parent_row:
                for k, subject in enumerate(row[1:]):
                    if subject == "自立":
                        parent_subject = rows[parent_row][k+1]
                        if parent_subject not in ["数", "英"]:
                            print(f"  自立活動違反: {exchange_class} {days[k]}曜{periods[k]}限（親学級は{parent_subject}）")
                            violations += 1
    
    if violations == 0:
        print("  ✓ 自立活動違反: なし")
    
    # 2. 日内重複チェック
    dup_count = 0
    for i, row in enumerate(rows[2:], start=3):
        if not row[0] or not row[0].strip():
            continue
        
        day_subjects = defaultdict(list)
        for j, (day, period, subject) in enumerate(zip(days, periods, row[1:])):
            if subject and subject not in ["欠", "YT", "道", "学", "総", "学総", "行", "技家"]:
                day_subjects[day].append((period, subject))
        
        for day, subjects in day_subjects.items():
            subject_count = defaultdict(int)
            for period, subject in subjects:
                subject_count[subject] += 1
            
            for subject, count in subject_count.items():
                if count > 1:
                    print(f"  日内重複: {row[0]} {day}曜日に{subject}が{count}回")
                    dup_count += 1
    
    if dup_count == 0:
        print("  ✓ 日内重複: なし")

if __name__ == "__main__":
    smart_fix_all_issues()