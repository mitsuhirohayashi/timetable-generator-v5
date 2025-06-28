#!/usr/bin/env python3
"""
全ての交流学級の自立活動と、画像のエラー表示との対応を確認
"""
import csv
from pathlib import Path

def check_all_jiritsu():
    """全ての自立活動をチェック"""
    # 交流学級と親学級の対応
    exchange_pairs = {
        "1年6組": "1年1組",
        "1年7組": "1年2組", 
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    # CSVファイルを読み込み
    csv_path = Path("data/output/output.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]
    periods = rows[1][1:]
    
    # 各クラスのデータを辞書に格納
    class_schedules = {}
    row_numbers = {}  # クラス名と行番号の対応
    for i, row in enumerate(rows[2:], start=3):  # 3行目から開始
        if row[0] and row[0].strip():
            class_name = row[0]
            schedule = row[1:]
            class_schedules[class_name] = schedule
            row_numbers[class_name] = i
    
    print("=== 交流学級の全ての自立活動 ===")
    
    for exchange_class in exchange_pairs.keys():
        if exchange_class not in class_schedules:
            continue
            
        print(f"\n{exchange_class} (行{row_numbers[exchange_class]}):")
        schedule = class_schedules[exchange_class]
        
        jiritsu_count = 0
        for i, (day, period, subject) in enumerate(zip(days, periods, schedule)):
            if subject == "自立":
                col_letter = chr(65 + (i + 1))  # A列はクラス名なので+1
                cell = f"{col_letter}{row_numbers[exchange_class]}"
                
                # 親学級の科目を確認
                parent_class = exchange_pairs[exchange_class]
                parent_subject = class_schedules[parent_class][i] if parent_class in class_schedules else "不明"
                
                status = "✓ OK" if parent_subject in ["数", "英"] else "× NG"
                print(f"  {day}曜{period}限: 自立 (親学級は{parent_subject}) {status} - セル{cell}")
                jiritsu_count += 1
        
        if jiritsu_count == 0:
            print("  自立活動なし")
    
    # D列（木曜日）の状況を確認
    print("\n=== D列（木曜日）の状況 ===")
    for exchange_class in exchange_pairs.keys():
        if exchange_class not in class_schedules:
            continue
            
        schedule = class_schedules[exchange_class]
        # D列は月、月、月、月、月、月、火...の7列目から（0ベース）
        thursday_indices = [i for i, d in enumerate(days) if d == "木"]
        
        for idx in thursday_indices:
            period = periods[idx]
            subject = schedule[idx]
            row = row_numbers[exchange_class]
            
            if subject == "自立":
                parent_class = exchange_pairs[exchange_class]
                parent_subject = class_schedules[parent_class][idx] if parent_class in class_schedules else "不明"
                print(f"D{row}: {exchange_class} 木曜{period}限 = {subject} (親学級は{parent_subject})")
    
    # 画像のエラー位置との対応を推測
    print("\n=== エラー位置の推測 ===")
    print("D12×の可能性:")
    if "2年5組" in row_numbers and row_numbers["2年5組"] == 12:
        print("  2年5組が12行目")
    if "2年6組" in row_numbers and row_numbers["2年6組"] == 13:
        print("  2年6組が13行目（近い）")
        
    print("\nD18×の可能性:")
    if "3年5組" in row_numbers and row_numbers["3年5組"] == 19:
        print("  3年5組が19行目（近い）")
    if "3年6組" in row_numbers and row_numbers["3年6組"] == 20:
        print("  3年6組が20行目（近い）")

if __name__ == "__main__":
    check_all_jiritsu()