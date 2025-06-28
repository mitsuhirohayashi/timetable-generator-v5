#!/usr/bin/env python3
"""
交流学級の自立活動違反を修正

交流学級が自立活動を行う時、親学級が数学または英語になるよう修正
"""
import csv
from pathlib import Path
import shutil

def fix_jiritsu_violations():
    """自立活動違反を修正"""
    # 交流学級と親学級の対応
    exchange_pairs = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    # バックアップを作成
    csv_path = Path("data/output/output.csv")
    backup_path = Path("data/output/output_backup_jiritsu.csv")
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
    
    print("\n=== 自立活動違反の修正 ===")
    
    # 違反を修正
    fixes = []
    
    # 1. 1年7組 火曜5限の自立（親学級1年2組は「家」）
    if "1年7組" in class_row_map and "1年2組" in class_row_map:
        exchange_row = class_row_map["1年7組"]
        parent_row = class_row_map["1年2組"]
        
        # 火曜5限のインデックスを見つける（0ベース）
        target_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "火" and period == "5":
                target_idx = i + 1  # +1はクラス名列のため
                break
        
        if target_idx and rows[exchange_row][target_idx] == "自立":
            # 親学級を数学に変更
            print(f"修正1: 1年2組の火曜5限を「家」→「数」に変更")
            rows[parent_row][target_idx] = "数"
            fixes.append("1年2組 火曜5限: 家→数")
    
    # 2. 2年7組 月曜5限の自立（親学級2年2組は「音」）
    if "2年7組" in class_row_map and "2年2組" in class_row_map:
        exchange_row = class_row_map["2年7組"]
        parent_row = class_row_map["2年2組"]
        
        # 月曜5限のインデックスを見つける
        target_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "月" and period == "5":
                target_idx = i + 1
                break
        
        if target_idx and rows[exchange_row][target_idx] == "自立":
            # 親学級を英語に変更
            print(f"修正2: 2年2組の月曜5限を「音」→「英」に変更")
            rows[parent_row][target_idx] = "英"
            fixes.append("2年2組 月曜5限: 音→英")
    
    # 3. 2年7組 水曜3限の自立（親学級2年2組は「保」）
    if "2年7組" in class_row_map and "2年2組" in class_row_map:
        exchange_row = class_row_map["2年7組"] 
        parent_row = class_row_map["2年2組"]
        
        # 水曜3限のインデックスを見つける
        target_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "水" and period == "3":
                target_idx = i + 1
                break
        
        if target_idx and rows[exchange_row][target_idx] == "自立":
            # 親学級を数学に変更
            print(f"修正3: 2年2組の水曜3限を「保」→「数」に変更")
            rows[parent_row][target_idx] = "数"
            fixes.append("2年2組 水曜3限: 保→数")
    
    # 4. 3年6組の月曜6限の空白を修正
    if "3年6組" in class_row_map:
        row = class_row_map["3年6組"]
        # 月曜6限のインデックスを見つける
        target_idx = None
        for i, (day, period) in enumerate(zip(days, periods)):
            if day == "月" and period == "6":
                target_idx = i + 1
                break
        
        if target_idx and not rows[row][target_idx]:
            # 3年3組と同じ科目（保）を設定
            parent_row = class_row_map.get("3年3組")
            if parent_row:
                parent_subject = rows[parent_row][target_idx]
                print(f"修正4: 3年6組の月曜6限を空白→「{parent_subject}」に設定")
                rows[row][target_idx] = parent_subject
                fixes.append(f"3年6組 月曜6限: 空白→{parent_subject}")
    
    # CSVファイルに書き込み
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\n修正完了: {len(fixes)}件")
    for fix in fixes:
        print(f"  - {fix}")
    
    # 修正後の確認
    print("\n=== 修正後の確認 ===")
    
    # 交流学級の自立活動を再チェック
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows_check = list(reader)
    
    violations = 0
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in class_row_map or parent_class not in class_row_map:
            continue
        
        exchange_row = class_row_map[exchange_class]
        parent_row = class_row_map[parent_class]
        
        for i, (day, period) in enumerate(zip(days, periods)):
            col_idx = i + 1
            if col_idx < len(rows_check[exchange_row]) and rows_check[exchange_row][col_idx] == "自立":
                parent_subject = rows_check[parent_row][col_idx] if col_idx < len(rows_check[parent_row]) else ""
                if parent_subject not in ["数", "英"]:
                    print(f"  違反残存: {exchange_class} {day}曜{period}限（親学級は{parent_subject}）")
                    violations += 1
    
    if violations == 0:
        print("  全ての自立活動違反が修正されました！")
    else:
        print(f"  {violations}件の違反が残っています")

if __name__ == "__main__":
    fix_jiritsu_violations()