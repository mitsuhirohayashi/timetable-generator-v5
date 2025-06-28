#!/usr/bin/env python3
"""テスト期間の授業を元に戻すスクリプト"""
import pandas as pd
from pathlib import Path


def fix_test_period_violations():
    """テスト期間に変更された授業を元のinput.csvの内容に戻す"""
    
    # ファイルパス
    input_path = Path("data/input/input.csv")
    output_path = Path("data/output/output.csv")
    
    # データ読み込み
    print("入力データを読み込み中...")
    input_df = pd.read_csv(input_path, header=None)
    output_df = pd.read_csv(output_path)
    
    # テスト期間のスロット（Follow-up.csvより）
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3), 
        ("水", 1), ("水", 2)
    ]
    
    print("\nテスト期間の授業を修正中...")
    
    # 出力データのヘッダー問題を修正
    # 月, 月.1, 月.2... という形式を正しいインデックスにマッピング
    day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
    
    for day, period in test_periods:
        # 入力データの列番号（1ベース + ヘッダー2行）
        input_col = day_map[day] + period
        
        # 出力データの列番号を特定
        # ヘッダーの重複により列名が変わっているため
        output_col = None
        col_names = output_df.columns.tolist()
        
        # 正しい列を探す
        target_col_index = day_map[day] + period - 1
        if target_col_index < len(col_names):
            output_col_name = col_names[target_col_index]
        else:
            continue
        
        # 各クラスの授業を修正
        for row_idx in range(2, len(input_df)):  # ヘッダー2行をスキップ
            class_name = input_df.iloc[row_idx, 0]
            
            if pd.isna(class_name) or class_name == "":
                continue
            
            # 入力データの授業
            input_subject = input_df.iloc[row_idx, input_col]
            
            # 出力データで対応する行を探す
            output_row = output_df[output_df.iloc[:, 0] == class_name].index
            
            if len(output_row) > 0:
                output_row_idx = output_row[0]
                current_subject = output_df.loc[output_row_idx, output_col_name]
                
                # 違いがある場合は修正
                if str(input_subject) != str(current_subject):
                    print(f"  {class_name} {day}曜{period}限: {current_subject} → {input_subject}")
                    output_df.loc[output_row_idx, output_col_name] = input_subject
    
    # CSVヘッダーを修正
    print("\nCSVヘッダーを修正中...")
    correct_headers = ["基本時間割"]
    for day in ["月", "火", "水", "木", "金"]:
        for _ in range(6):
            correct_headers.append(day)
    
    output_df.columns = correct_headers[:len(output_df.columns)]
    
    # 保存
    print("\n修正済みデータを保存中...")
    output_df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"保存完了: {output_path}")


if __name__ == "__main__":
    fix_test_period_violations()