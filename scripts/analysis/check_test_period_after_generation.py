#!/usr/bin/env python3
"""生成後の時間割でテスト期間データが保持されているか確認"""

import csv
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

def check_test_periods_in_csv(csv_path):
    """CSVファイル内のテスト期間データを確認"""
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    # 曜日から列インデックスへのマッピング
    day_to_col_offset = {"月": 0, "火": 6, "水": 12, "木": 18, "金": 24}
    
    print(f"\n=== {csv_path} のテスト期間データを確認 ===\n")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if len(rows) < 3:
        print("CSVファイルの形式が正しくありません")
        return
    
    # 各テスト期間のデータをチェック
    for day, period in test_periods:
        print(f"\n{day}曜{period}限:")
        col_index = day_to_col_offset[day] + period  # 0-indexed
        
        count = 0
        subjects = []
        for row_idx, row in enumerate(rows[2:], 2):  # 3行目から（クラスデータ）
            if len(row) > col_index:
                subject = row[col_index].strip()
                if subject and subject != "0":
                    class_name = row[0].strip()
                    count += 1
                    subjects.append(f"  {class_name}: {subject}")
        
        print(f"  配置数: {count}クラス")
        if count > 0:
            for subj in subjects[:5]:  # 最初の5件
                print(subj)
            if len(subjects) > 5:
                print(f"  ... 他 {len(subjects) - 5} クラス")

def main():
    # 入力ファイルと出力ファイルを比較
    input_csv = Path("data/input/input.csv")
    output_csv = Path("data/output/output.csv")
    
    if input_csv.exists():
        check_test_periods_in_csv(input_csv)
    else:
        print(f"{input_csv} が見つかりません")
    
    if output_csv.exists():
        check_test_periods_in_csv(output_csv)
    else:
        print(f"\n{output_csv} が見つかりません")
        print("時間割を生成してから再度実行してください")

if __name__ == "__main__":
    main()