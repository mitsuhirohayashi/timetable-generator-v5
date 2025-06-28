#!/usr/bin/env python3
"""月曜6限をinput.csvの内容（YT）に復元する"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def restore_monday_6th_yt():
    """月曜6限をinput.csvの内容に復元"""
    print("=== 月曜6限をinput.csvの内容に復元 ===\n")
    
    # input.csvを読み込む
    input_path = path_config.input_dir / "input.csv"
    print(f"Reading original schedule from: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        input_data = list(reader)
    
    # output.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading current schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        output_data = list(reader)
    
    # 月曜6限の列インデックス（0-indexed）
    monday_6th_col_idx = 6
    
    # 各行を処理
    restored_count = 0
    for idx, (input_row, output_row) in enumerate(zip(input_data, output_data)):
        if idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = output_row[0] if output_row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
            
        # 月曜6限を復元
        if len(input_row) > monday_6th_col_idx and len(output_row) > monday_6th_col_idx:
            input_value = input_row[monday_6th_col_idx]
            output_value = output_row[monday_6th_col_idx]
            
            # input.csvの値と異なる場合は復元
            if input_value and input_value != output_value:
                print(f"Restoring {class_name}: {output_value} → {input_value}")
                output_data[idx][monday_6th_col_idx] = input_value
                restored_count += 1
    
    # 修正後のデータを保存
    if restored_count > 0:
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
        print(f"Restored {restored_count} Monday 6th period values")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("No Monday 6th period restorations needed")
    
    return restored_count


if __name__ == "__main__":
    restored_count = restore_monday_6th_yt()
    print(f"\nTotal values restored: {restored_count}")
    print("\n固定科目の絶対的優先ルールが適用されました。")
    print("今後、input.csvの内容は制約システムよりも優先されます。")