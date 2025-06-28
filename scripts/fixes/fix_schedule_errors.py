#!/usr/bin/env python3
"""
D12×とD18×のエラーを修正
- 2年5組（行12）: 数学が3時間で不足
- 3年3組（行18）: 月曜に保が2回（日内重複）、数学と国語が不足
"""
import csv
from pathlib import Path
import shutil

def fix_schedule_errors():
    """スケジュールのエラーを修正"""
    # バックアップを作成
    csv_path = Path("data/output/output.csv")
    backup_path = Path("data/output/output_backup_d_errors.csv")
    shutil.copy(csv_path, backup_path)
    print(f"バックアップを作成: {backup_path}")
    
    # CSVファイルを読み込み
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]
    periods = rows[1][1:]
    
    print("\n=== エラーの修正 ===")
    
    # 1. 3年3組（行18）の月曜日の保重複を修正
    row_3_3 = 17  # 0ベースで17（1ベースで18）
    monday_indices = [i+1 for i, d in enumerate(days) if d == "月"]
    
    # 月曜の保を確認
    monday_pe_count = 0
    pe_positions = []
    for idx in monday_indices:
        if rows[row_3_3][idx] == "保":
            monday_pe_count += 1
            pe_positions.append((idx, periods[idx-1]))
    
    if monday_pe_count > 1:
        print(f"修正1: 3年3組の月曜日の保重複（{monday_pe_count}回）")
        # 月曜5限の保を国に変更（国語が不足しているため）
        for idx, period in pe_positions:
            if period == "5":
                print(f"  月曜{period}限: 保→国")
                rows[row_3_3][idx] = "国"
                break
    
    # 2. 2年5組（行12）の数学不足を修正
    row_2_5 = 11  # 0ベースで11（1ベースで12）
    
    # 現在の数学の時数を確認
    math_count = 0
    for subject in rows[row_2_5][1:]:
        if subject == "数":
            math_count += 1
    
    if math_count < 4:
        print(f"\n修正2: 2年5組の数学不足（現在{math_count}時間）")
        # 木曜1限の作業を数に変更
        thursday_1_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "木" and period == "1":
                thursday_1_idx = i + 1
                break
        
        if thursday_1_idx and rows[row_2_5][thursday_1_idx] == "作業":
            print(f"  木曜1限: 作業→数")
            rows[row_2_5][thursday_1_idx] = "数"
    
    # 3. 3年3組（行18）の数学不足を修正
    math_count_3_3 = 0
    for subject in rows[row_3_3][1:]:
        if subject == "数":
            math_count_3_3 += 1
    
    if math_count_3_3 < 4:
        print(f"\n修正3: 3年3組の数学不足（現在{math_count_3_3}時間）")
        # 金曜2限の理を数に変更
        friday_2_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "金" and period == "2":
                friday_2_idx = i + 1
                break
        
        if friday_2_idx and rows[row_3_3][friday_2_idx] == "理":
            print(f"  金曜2限: 理→数")
            rows[row_3_3][friday_2_idx] = "数"
    
    # CSVファイルに書き込み
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print("\n=== 修正後の確認 ===")
    
    # 修正後の時数を確認
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows_check = list(reader)
    
    # 2年5組の数学
    math_count_2_5 = 0
    for subject in rows_check[11][1:]:
        if subject == "数":
            math_count_2_5 += 1
    print(f"2年5組の数学: {math_count_2_5}時間")
    
    # 3年3組の数学と国語
    math_count_3_3 = 0
    japanese_count_3_3 = 0
    pe_monday_3_3 = 0
    
    for i, subject in enumerate(rows_check[17][1:]):
        if subject == "数":
            math_count_3_3 += 1
        elif subject == "国":
            japanese_count_3_3 += 1
        elif subject == "保" and days[i] == "月":
            pe_monday_3_3 += 1
    
    print(f"3年3組の数学: {math_count_3_3}時間")
    print(f"3年3組の国語: {japanese_count_3_3}時間")
    print(f"3年3組の月曜体育: {pe_monday_3_3}回")
    
    print("\n修正完了！")

if __name__ == "__main__":
    fix_schedule_errors()