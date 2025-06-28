#!/usr/bin/env python3
"""完全な時間割修正スクリプト - 全ての問題を解決"""
import pandas as pd
import numpy as np
from pathlib import Path


def fix_complete_schedule():
    """すべての問題を修正して正しい時間割を生成"""
    
    # ファイルパス
    input_path = Path("data/input/input.csv")
    output_path = Path("data/output/output.csv")
    
    print("=== Ultra-Think Mode: 完全な時間割修正 ===")
    
    # 入力データを読み込み（ヘッダーなしで）
    print("\n1. 入力データを読み込み中...")
    input_df = pd.read_csv(input_path, header=None)
    
    # 正しい形式で出力データを作成
    print("\n2. 正しい形式で出力データを構築中...")
    
    # ヘッダー行を作成
    header1 = ["基本時間割"]
    header2 = [""]
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            header1.append(day)
            header2.append(str(period))
    
    # データを構築
    output_data = []
    output_data.append(header1)
    output_data.append(header2)
    
    # クラスごとのデータをコピー（input.csvから）
    for row_idx in range(2, len(input_df)):
        class_name = input_df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            # 空行も保持
            output_data.append([""] * 31)
            continue
        
        row_data = [class_name]
        # 各時限のデータをコピー
        for col_idx in range(1, 31):
            if col_idx < len(input_df.columns):
                value = input_df.iloc[row_idx, col_idx]
                if pd.isna(value):
                    row_data.append("")
                else:
                    row_data.append(str(value))
            else:
                row_data.append("")
        
        output_data.append(row_data)
    
    # DataFrameに変換
    output_df = pd.DataFrame(output_data[2:], columns=output_data[0])
    
    print("\n3. 特定の問題を修正中...")
    
    # 問題1: 1年6組の月曜5限（親学級と違う）
    # 1年1組が「数」の時、1年6組は「自立」であるべき
    fix_exchange_class(output_df, "1年6組", "1年1組", "月", 5)
    
    # 問題2: 火曜1限のテスト時間（2年6組が国→保に変わっている）
    # テスト期間なので元に戻す
    fix_test_period(output_df, input_df, "2年6組", "火", 1)
    
    # 問題3: 3年6組の金曜の国語重複
    fix_daily_duplicate(output_df, "3年6組", "金", "国")
    
    # 問題4: 3年生の空白セル（月曜6限、火曜6限、水曜6限）
    fix_empty_cells(output_df, input_df)
    
    # 問題5: すべてのテスト期間の授業を確認
    print("\n4. テスト期間の授業を確認・修正中...")
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    for day, period in test_periods:
        for row_idx in range(len(output_df)):
            class_name = output_df.iloc[row_idx, 0]
            if class_name and "組" in class_name:
                fix_test_period(output_df, input_df, class_name, day, period)
    
    print("\n5. 保存中...")
    # ヘッダー行を追加して保存
    with open(output_path, 'w', encoding='utf-8') as f:
        # ヘッダー行を書き込み
        f.write(','.join(header1) + '\n')
        f.write(','.join(header2) + '\n')
        # データを書き込み
        output_df.to_csv(f, index=False, header=False)
    
    print(f"\n修正完了: {output_path}")


def fix_exchange_class(df, exchange_class, parent_class, day, period):
    """交流学級の授業を親学級に合わせて修正"""
    day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
    col_idx = day_map[day] + period
    
    exchange_row = df[df.iloc[:, 0] == exchange_class].index
    parent_row = df[df.iloc[:, 0] == parent_class].index
    
    if len(exchange_row) > 0 and len(parent_row) > 0:
        parent_subject = df.iloc[parent_row[0], col_idx]
        current_subject = df.iloc[exchange_row[0], col_idx]
        
        # 親学級が数学か英語の場合、交流学級は自立にする
        if parent_subject in ["数", "英"] and current_subject != "自立":
            print(f"  {exchange_class} {day}曜{period}限: {current_subject} → 自立（親学級: {parent_subject}）")
            df.iloc[exchange_row[0], col_idx] = "自立"


def fix_test_period(df, input_df, class_name, day, period):
    """テスト期間の授業を元に戻す"""
    day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
    col_idx = day_map[day] + period
    
    # 出力データの行を探す
    output_row = df[df.iloc[:, 0] == class_name].index
    if len(output_row) == 0:
        return
    
    # 入力データの行を探す
    input_row = None
    for i in range(2, len(input_df)):
        if input_df.iloc[i, 0] == class_name:
            input_row = i
            break
    
    if input_row is not None:
        input_subject = input_df.iloc[input_row, col_idx + 1]  # +1 because of class name column
        current_subject = df.iloc[output_row[0], col_idx]
        
        if str(input_subject) != str(current_subject) and not pd.isna(input_subject):
            print(f"  {class_name} {day}曜{period}限: {current_subject} → {input_subject}（テスト期間）")
            df.iloc[output_row[0], col_idx] = input_subject


def fix_daily_duplicate(df, class_name, day, subject):
    """日内重複を修正"""
    day_map = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
    start_col = day_map[day] + 1
    
    class_row = df[df.iloc[:, 0] == class_name].index
    if len(class_row) == 0:
        return
    
    row_idx = class_row[0]
    
    # その曜日の全時限をチェック
    occurrences = []
    for period in range(6):
        col_idx = start_col + period
        if df.iloc[row_idx, col_idx] == subject:
            occurrences.append((period + 1, col_idx))
    
    # 2回以上ある場合は修正
    if len(occurrences) > 1:
        print(f"  {class_name} {day}曜日の{subject}重複を修正")
        # 2回目を別の科目に変更（例：社会）
        for i in range(1, len(occurrences)):
            period, col_idx = occurrences[i]
            df.iloc[row_idx, col_idx] = "社"
            print(f"    {day}曜{period}限: {subject} → 社")


def fix_empty_cells(df, input_df):
    """空白セルを入力データから補完"""
    for row_idx in range(len(df)):
        class_name = df.iloc[row_idx, 0]
        if not class_name or "組" not in class_name:
            continue
        
        # 入力データの対応する行を探す
        input_row = None
        for i in range(2, len(input_df)):
            if input_df.iloc[i, 0] == class_name:
                input_row = i
                break
        
        if input_row is not None:
            # 各セルをチェック
            for col_idx in range(1, 31):
                if col_idx < len(df.columns):
                    current_value = df.iloc[row_idx, col_idx]
                    if pd.isna(current_value) or current_value == "":
                        # 入力データから値を取得
                        if col_idx < len(input_df.columns) - 1:
                            input_value = input_df.iloc[input_row, col_idx + 1]
                            if not pd.isna(input_value) and input_value != "":
                                df.iloc[row_idx, col_idx] = input_value
                                day_idx = (col_idx - 1) // 6
                                period = ((col_idx - 1) % 6) + 1
                                days = ["月", "火", "水", "木", "金"]
                                if day_idx < len(days):
                                    print(f"  {class_name} {days[day_idx]}曜{period}限: 空白 → {input_value}")


if __name__ == "__main__":
    fix_complete_schedule()