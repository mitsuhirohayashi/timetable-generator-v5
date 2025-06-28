#!/usr/bin/env python3
"""テスト期間の教科変更をチェックするスクリプト"""
import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser


def main():
    """テスト期間の教科変更をチェック"""
    # ファイルパス
    input_path = project_root / "data" / "input" / "input.csv"
    output_path = project_root / "data" / "output" / "output.csv"
    followup_path = project_root / "data" / "input" / "Follow-up.csv"
    
    # Follow-up.csvからテスト期間を読み取り
    parser = EnhancedFollowUpParser(followup_path.parent)
    result = parser.parse_file(followup_path.name)
    
    test_periods = {}
    if result.get("test_periods"):
        for test_period in result["test_periods"]:
            day = test_period.day
            for period in test_period.periods:
                test_periods[(day, period)] = test_period.reason if hasattr(test_period, 'reason') else "テスト期間"
    
    print(f"テスト期間: {len(test_periods)}スロット")
    for (day, period), reason in test_periods.items():
        print(f"  - {day}曜{period}限: {reason}")
    
    # CSVファイルを読み込み
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        input_rows = list(reader)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        output_rows = list(reader)
    
    # テスト期間の変更をチェック
    print("\n=== テスト期間の教科変更チェック ===")
    
    changes = []
    day_map = {"月": 1, "火": 7, "水": 13, "木": 19, "金": 25}
    
    for (day, period) in test_periods.keys():
        if day not in day_map:
            continue
        
        col = day_map[day] + period - 1
        
        print(f"\n{day}曜{period}限:")
        
        # 各クラスをチェック
        for row_idx in range(2, min(len(input_rows), len(output_rows))):
            if input_rows[row_idx][0] == "" or output_rows[row_idx][0] == "":
                continue
            
            class_name = input_rows[row_idx][0]
            input_subject = input_rows[row_idx][col] if col < len(input_rows[row_idx]) else ""
            output_subject = output_rows[row_idx][col] if col < len(output_rows[row_idx]) else ""
            
            if input_subject != output_subject:
                print(f"  {class_name}: {input_subject} → {output_subject} 【変更あり】")
                changes.append((class_name, day, period, input_subject, output_subject))
            else:
                print(f"  {class_name}: {input_subject} (変更なし)")
    
    print(f"\n=== 結果サマリー ===")
    print(f"テスト期間総スロット数: {len(test_periods) * 19}個（{len(test_periods)}時限 × 19クラス）")
    print(f"変更されたスロット数: {len(changes)}個")
    if changes:
        print(f"変更率: {len(changes) / (len(test_periods) * 19) * 100:.1f}%")
        
        print("\n変更詳細:")
        for class_name, day, period, before, after in changes:
            print(f"  - {class_name} {day}曜{period}限: {before} → {after}")


if __name__ == "__main__":
    main()