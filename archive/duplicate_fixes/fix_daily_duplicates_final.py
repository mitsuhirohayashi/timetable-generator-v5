#!/usr/bin/env python3
"""最後の日内重複を修正"""

import csv
from collections import Counter

def fix_duplicates():
    """日内重複を修正"""
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    day_row = rows[0]
    period_row = rows[1]
    
    print("=== 日内重複の修正 ===")
    
    # 3年1組の月曜日の理の重複
    for row_idx, row in enumerate(rows):
        if len(row) > 0 and row[0] == "3年1組":
            # 月曜日の科目を収集
            mon_subjects = []
            mon_cols = []
            for col_idx, (day, period) in enumerate(zip(day_row, period_row)):
                if day == "月" and col_idx < len(row):
                    mon_subjects.append((col_idx, period, row[col_idx]))
                    mon_cols.append(col_idx)
            
            # 理が2回あるか確認
            science_count = sum(1 for _, _, subj in mon_subjects if subj == "理")
            if science_count >= 2:
                # 2つ目の理を別の科目に変更
                found_first = False
                for col_idx, period, subj in mon_subjects:
                    if subj == "理":
                        if found_first:
                            row[col_idx] = "英"  # 英語に変更
                            print(f"3年1組 月曜{period}限: 理→英")
                            break
                        else:
                            found_first = True
            break
    
    # 3年2組の火曜日の数の重複
    for row_idx, row in enumerate(rows):
        if len(row) > 0 and row[0] == "3年2組":
            # 火曜日の科目を収集
            tue_subjects = []
            for col_idx, (day, period) in enumerate(zip(day_row, period_row)):
                if day == "火" and col_idx < len(row):
                    tue_subjects.append((col_idx, period, row[col_idx]))
            
            # 数が2回あるか確認
            math_count = sum(1 for _, _, subj in tue_subjects if subj == "数")
            if math_count >= 2:
                # 2つ目の数を別の科目に変更
                found_first = False
                for col_idx, period, subj in tue_subjects:
                    if subj == "数":
                        if found_first:
                            row[col_idx] = "国"  # 国語に変更
                            print(f"3年2組 火曜{period}限: 数→国")
                            break
                        else:
                            found_first = True
            break
    
    # 3年6組の月曜日の国の重複
    for row_idx, row in enumerate(rows):
        if len(row) > 0 and row[0] == "3年6組":
            # 月曜日の科目を収集
            mon_subjects = []
            for col_idx, (day, period) in enumerate(zip(day_row, period_row)):
                if day == "月" and col_idx < len(row):
                    mon_subjects.append((col_idx, period, row[col_idx]))
            
            # 国が2回あるか確認
            jpn_count = sum(1 for _, _, subj in mon_subjects if subj == "国")
            if jpn_count >= 2:
                # 2つ目の国を別の科目に変更
                found_first = False
                for col_idx, period, subj in mon_subjects:
                    if subj == "国":
                        if found_first:
                            row[col_idx] = "音"  # 音楽に変更
                            print(f"3年6組 月曜{period}限: 国→音")
                            break
                        else:
                            found_first = True
            break
    
    # ファイルに保存
    with open("data/output/output.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print("\ndata/output/output.csv を更新しました")

if __name__ == "__main__":
    fix_duplicates()