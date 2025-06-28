#!/usr/bin/env python3
"""input.csvの内容を尊重し、固定科目を復元する"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def restore_original_fixed_subjects():
    """input.csvの固定科目を復元する"""
    print("=== 固定科目の復元 ===")
    print("input.csvの内容を尊重し、固定科目を元に戻します\n")
    
    # input.csvを読み込む
    input_path = path_config.data_dir / "input" / "input.csv"
    print(f"Reading original from: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        input_data = list(reader)
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading current from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        output_data = list(reader)
    
    # 固定科目のリスト
    fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
    
    # 修正件数
    fixed_count = 0
    
    # 各セルをチェックして固定科目を復元
    for row_idx in range(2, len(input_data)):  # ヘッダー行をスキップ
        if row_idx >= len(output_data):
            break
            
        input_row = input_data[row_idx]
        output_row = output_data[row_idx]
        
        # 空白行はスキップ
        if not input_row or not input_row[0] or not output_row or not output_row[0]:
            continue
        
        class_name = input_row[0]
        
        # 各列をチェック
        for col_idx in range(1, min(len(input_row), len(output_row))):
            input_subject = input_row[col_idx] if col_idx < len(input_row) else ""
            output_subject = output_row[col_idx] if col_idx < len(output_row) else ""
            
            # input.csvに固定科目がある場合
            if input_subject in fixed_subjects:
                if output_subject != input_subject:
                    print(f"Restoring {class_name} col{col_idx}: {output_subject} → {input_subject}")
                    output_row[col_idx] = input_subject
                    fixed_count += 1
    
    # 月曜6校時の特別チェック（1・2年生はYT）
    print("\n月曜6校時の確認:")
    monday_6th_col = 6
    
    for row_idx in range(2, len(output_data)):
        if row_idx >= len(output_data):
            break
            
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
            
        class_name = row[0]
        
        # 1・2年生のクラスを確認
        if '年' in class_name:
            try:
                grade = int(class_name.split('年')[0])
                
                if grade in [1, 2] and len(row) > monday_6th_col:
                    # input.csvの同じクラスを探す
                    for input_row in input_data:
                        if input_row and input_row[0] == class_name:
                            if len(input_row) > monday_6th_col and input_row[monday_6th_col] == "YT":
                                if row[monday_6th_col] != "YT":
                                    print(f"  Restoring {class_name} Monday 6th: {row[monday_6th_col]} → YT")
                                    row[monday_6th_col] = "YT"
                                    fixed_count += 1
                            break
            except (ValueError, IndexError):
                continue
    
    # 修正後のデータを保存
    if fixed_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_restore_yt')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(output_data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(output_data)
        print(f"Restored {fixed_count} fixed subjects")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("\nNo fixed subjects need restoration")
    
    return fixed_count


if __name__ == "__main__":
    fixed_count = restore_original_fixed_subjects()
    print(f"\nTotal subjects restored: {fixed_count}")
    print("\nCLAUDE.mdのルール:")
    print("- 固定科目は「保護」するのみで「強制」はしない")
    print("- input.csvに入力されている内容を完全に尊重する")