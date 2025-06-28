#!/usr/bin/env python3
"""テスト期間のデータ消失を調査するシンプルなデバッグスクリプト"""

import pandas as pd

def check_test_periods():
    """テスト期間のデータを確認（pandas使用）"""
    
    # テスト期間の定義（Follow-up.csvから）
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),  # 月曜1-3校時
        ("火", 1), ("火", 2), ("火", 3),  # 火曜1-3校時
        ("水", 1), ("水", 2)               # 水曜1-2校時
    ]
    
    print("=== テスト期間データ確認 ===\n")
    
    # input.csvを読み込み
    print("1. input.csv の内容:")
    print("-" * 50)
    
    input_df = pd.read_csv("data/input/input.csv")
    
    # 各クラスの行を処理
    for idx in range(2, len(input_df)):  # 3行目から開始
        class_name = input_df.iloc[idx, 0]
        if pd.isna(class_name) or class_name.strip() == "":
            continue
        
        # テスト期間のデータを表示
        for day_idx, (day, period) in enumerate(test_periods):
            # カラムインデックスを計算
            day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
            col_idx = day_map[day] + int(period)
            
            subject = input_df.iloc[idx, col_idx]
            if not pd.isna(subject) and subject.strip() != "":
                print(f"  {class_name} - {day}曜{period}限: {subject}")
    
    # output.csvを読み込み
    print("\n\n2. output.csv の内容:")
    print("-" * 50)
    
    try:
        output_df = pd.read_csv("data/output/output.csv")
        
        # 各クラスの行を処理
        for idx in range(2, len(output_df)):  # 3行目から開始
            class_name = output_df.iloc[idx, 0]
            if pd.isna(class_name) or class_name.strip() == "":
                continue
            
            # テスト期間のデータを表示
            missing_subjects = []
            for day_idx, (day, period) in enumerate(test_periods):
                # カラムインデックスを計算
                day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
                col_idx = day_map[day] + int(period)
                
                subject = output_df.iloc[idx, col_idx]
                if pd.isna(subject) or subject.strip() == "":
                    # input.csvの同じセルを確認
                    input_row_idx = None
                    for i in range(2, len(input_df)):
                        if input_df.iloc[i, 0] == class_name:
                            input_row_idx = i
                            break
                    
                    if input_row_idx is not None:
                        input_subject = input_df.iloc[input_row_idx, col_idx]
                        if not pd.isna(input_subject) and input_subject.strip() != "":
                            missing_subjects.append(f"{day}曜{period}限: {input_subject}")
            
            if missing_subjects:
                print(f"\n❌ {class_name}で失われたデータ:")
                for subj in missing_subjects:
                    print(f"    - {subj}")
    
    except Exception as e:
        print(f"output.csv の読み込みエラー: {e}")
    
    # 集計
    print("\n\n3. 集計:")
    print("-" * 50)
    
    # input.csvのテスト期間のデータ数を数える
    input_test_count = 0
    for idx in range(2, len(input_df)):
        for day, period in test_periods:
            day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
            col_idx = day_map[day] + int(period)
            subject = input_df.iloc[idx, col_idx]
            if not pd.isna(subject) and subject.strip() != "":
                input_test_count += 1
    
    # output.csvのテスト期間のデータ数を数える
    output_test_count = 0
    try:
        for idx in range(2, len(output_df)):
            for day, period in test_periods:
                day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
                col_idx = day_map[day] + int(period)
                subject = output_df.iloc[idx, col_idx]
                if not pd.isna(subject) and subject.strip() != "":
                    output_test_count += 1
    except:
        output_test_count = 0
    
    print(f"input.csv のテスト期間データ数: {input_test_count}")
    print(f"output.csv のテスト期間データ数: {output_test_count}")
    print(f"失われたデータ数: {input_test_count - output_test_count}")

if __name__ == "__main__":
    check_test_periods()