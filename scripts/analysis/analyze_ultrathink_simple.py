#!/usr/bin/env python3
"""UltrathinkPerfectGeneratorの問題分析（簡略版）"""

import pandas as pd
from pathlib import Path

def analyze_issues():
    """問題を分析"""
    print("=== UltrathinkPerfectGenerator問題分析 ===\n")
    
    # 1. 入力CSVの分析
    print("【入力CSV（input.csv）の分析】")
    input_df = pd.read_csv("data/input/input.csv", header=None)
    print(f"入力サイズ: {input_df.shape}")
    
    # 空きセルのカウント
    empty_count = 0
    total_count = 0
    for i in range(input_df.shape[0]):
        for j in range(1, input_df.shape[1]):  # 最初の列はクラス名
            total_count += 1
            cell = input_df.iloc[i, j]
            if pd.isna(cell) or str(cell).strip() == "":
                empty_count += 1
    
    print(f"総セル数: {total_count}")
    print(f"空きセル数: {empty_count} ({empty_count/total_count*100:.1f}%)")
    print(f"埋まっているセル数: {total_count - empty_count}")
    
    # 2. 出力CSVの分析
    print("\n【出力CSV（output.csv）の分析】")
    output_df = pd.read_csv("data/output/output.csv", header=None)
    print(f"出力サイズ: {output_df.shape}")
    
    # 空きセルのカウント
    output_empty_count = 0
    output_total_count = 0
    for i in range(output_df.shape[0]):
        for j in range(1, output_df.shape[1]):  # 最初の列はクラス名
            output_total_count += 1
            cell = output_df.iloc[i, j]
            if pd.isna(cell) or str(cell).strip() == "":
                output_empty_count += 1
    
    print(f"総セル数: {output_total_count}")
    print(f"空きセル数: {output_empty_count} ({output_empty_count/output_total_count*100:.1f}%)")
    print(f"埋まっているセル数: {output_total_count - output_empty_count}")
    
    # 3. 差分分析
    print("\n【入力と出力の差分】")
    print(f"追加されたセル数: {(output_total_count - output_empty_count) - (total_count - empty_count)}")
    
    # 4. テスト期間の確認
    print("\n【テスト期間セルの確認】")
    test_cells = []
    days = ["月", "火", "水", "木", "金"]
    periods = ["1", "2", "3", "4", "5", "6"]
    
    # テスト期間のセルを確認（月曜1-3限、火曜1-3限、水曜1-2限）
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    print("入力CSVのテスト期間セル:")
    for i in range(input_df.shape[0]):
        class_name = input_df.iloc[i, 0]
        if pd.isna(class_name):
            continue
        
        for day_idx, day in enumerate(days):
            for period_idx, period in enumerate(periods):
                if (day, period_idx + 1) in test_periods:
                    col_idx = day_idx * 6 + period_idx + 1
                    if col_idx < input_df.shape[1]:
                        cell = input_df.iloc[i, col_idx]
                        if not pd.isna(cell) and str(cell).strip() != "":
                            print(f"  {class_name} {day}{period}: {cell}")
    
    # 5. 自立活動の確認
    print("\n【自立活動の確認】")
    jiritsu_count = {}
    exchange_classes = ["1-6", "1-7", "2-6", "2-7", "3-6", "3-7"]
    
    for i in range(input_df.shape[0]):
        class_name = str(input_df.iloc[i, 0]).strip()
        if class_name in exchange_classes:
            count = 0
            for j in range(1, input_df.shape[1]):
                cell = input_df.iloc[i, j]
                if not pd.isna(cell) and "自立" in str(cell):
                    count += 1
            jiritsu_count[class_name] = count
    
    print("入力CSVの交流学級の自立活動時数:")
    for class_name, count in sorted(jiritsu_count.items()):
        print(f"  {class_name}: {count}時間")
    
    # 6. 固定科目の確認
    print("\n【固定科目の確認】")
    fixed_subjects = ["欠", "YT", "学", "道", "総", "行"]
    fixed_count = 0
    
    for i in range(input_df.shape[0]):
        for j in range(1, input_df.shape[1]):
            cell = input_df.iloc[i, j]
            if not pd.isna(cell):
                for subject in fixed_subjects:
                    if subject in str(cell):
                        fixed_count += 1
                        break
    
    print(f"固定科目セル数: {fixed_count}")
    
    # 7. Follow-up.csvの確認
    print("\n【Follow-up.csvの確認】")
    followup_path = Path("data/input/Follow-up.csv")
    if followup_path.exists():
        with open(followup_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"Follow-up.csv行数: {len(lines)}")
            print("最初の5行:")
            for i, line in enumerate(lines[:5]):
                print(f"  {i+1}: {line.strip()}")

if __name__ == "__main__":
    analyze_issues()