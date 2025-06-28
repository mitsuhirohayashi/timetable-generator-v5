#!/usr/bin/env python3
"""空きスロットが埋まらない問題を簡単にデバッグ"""

import csv
from pathlib import Path

def count_empty_slots():
    """入力と出力のCSVファイルを比較して空きスロットを数える"""
    
    input_file = Path("data/input/input.csv")
    output_file = Path("data/output/output.csv")
    
    # CSVファイルを読み込む
    def read_csv(file_path):
        data = {}
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # ヘッダー行
            periods = next(reader)  # 校時行
            
            for row in reader:
                if not row or not row[0]:  # 空行をスキップ
                    continue
                class_name = row[0]
                data[class_name] = row[1:]  # 授業データ
        
        return data
    
    # 入力と出力を読み込む
    print("=== 入力ファイルの読み込み ===")
    input_data = read_csv(input_file)
    print(f"入力クラス数: {len(input_data)}")
    
    print("\n=== 出力ファイルの読み込み ===")
    output_data = read_csv(output_file)
    print(f"出力クラス数: {len(output_data)}")
    
    # 統計情報を計算
    total_slots = 0
    input_filled = 0
    output_filled = 0
    
    for class_name in input_data:
        if class_name not in output_data:
            print(f"警告: {class_name}が出力に存在しません")
            continue
        
        input_row = input_data[class_name]
        output_row = output_data[class_name]
        
        for i in range(min(len(input_row), len(output_row))):
            total_slots += 1
            if input_row[i].strip():
                input_filled += 1
            if output_row[i].strip():
                output_filled += 1
    
    print(f"\n=== 統計 ===")
    print(f"総スロット数: {total_slots}")
    print(f"入力の埋まったスロット: {input_filled} ({input_filled/total_slots*100:.1f}%)")
    print(f"出力の埋まったスロット: {output_filled} ({output_filled/total_slots*100:.1f}%)")
    print(f"削減されたスロット: {input_filled - output_filled}")
    
    # クラスごとの詳細
    print("\n=== クラスごとの詳細 ===")
    for class_name in sorted(input_data.keys()):
        if class_name not in output_data:
            continue
        
        input_row = input_data[class_name]
        output_row = output_data[class_name]
        
        input_count = sum(1 for x in input_row if x.strip())
        output_count = sum(1 for x in output_row if x.strip())
        
        if input_count != output_count:
            print(f"{class_name}: 入力{input_count} → 出力{output_count} (差{output_count - input_count})")
    
    # 空きスロットの詳細分析
    print("\n=== 空きスロットの位置分析 ===")
    days = ["月", "火", "水", "木", "金"]
    periods = range(1, 7)
    
    empty_by_day_period = {}
    for d, day in enumerate(days):
        for period in periods:
            slot_idx = d * 6 + (period - 1)
            empty_count = 0
            
            for class_name in output_data:
                if slot_idx < len(output_data[class_name]):
                    if not output_data[class_name][slot_idx].strip():
                        empty_count += 1
            
            empty_by_day_period[f"{day}{period}"] = empty_count
    
    print("曜日・時限別の空きスロット数:")
    for day in days:
        row = []
        for period in periods:
            count = empty_by_day_period[f"{day}{period}"]
            row.append(f"{count:2d}")
        print(f"{day}: {' '.join(row)}")
    
    # 特定の問題を確認
    print("\n=== 特定の問題確認 ===")
    print("3年生の月火水6限の状況:")
    for class_name in sorted(output_data.keys()):
        if class_name.startswith("3年"):
            # 月6、火6、水6のインデックスは5, 11, 17
            mon6 = output_data[class_name][5] if len(output_data[class_name]) > 5 else ""
            tue6 = output_data[class_name][11] if len(output_data[class_name]) > 11 else ""
            wed6 = output_data[class_name][17] if len(output_data[class_name]) > 17 else ""
            
            if not mon6 or not tue6 or not wed6:
                print(f"{class_name}: 月6='{mon6}', 火6='{tue6}', 水6='{wed6}'")

def main():
    """メイン処理"""
    print("空きスロット問題の簡単なデバッグ\n")
    count_empty_slots()

if __name__ == "__main__":
    main()