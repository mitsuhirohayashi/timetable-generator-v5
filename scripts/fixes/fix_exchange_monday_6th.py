#!/usr/bin/env python3
"""交流学級の月曜6校時を「欠」に修正"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def fix_exchange_monday_6th():
    """交流学級（6組・7組）の月曜6校時を「欠」に修正"""
    print("=== 交流学級の月曜6校時制約違反を修正 ===")
    print("1・2年生の交流学級（6組・7組）の月曜6校時を「欠」に変更します\n")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 月曜6校時の列インデックス（0-indexed）
    monday_6th_col_idx = 6
    
    # 修正対象クラス
    target_classes = [
        "1年6組", "1年7組",  # 1年生の交流学級
        "2年6組", "2年7組"   # 2年生の交流学級
    ]
    
    # 各行を処理
    violations_fixed = 0
    for idx, row in enumerate(data):
        if idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
            
        # 対象クラスの場合
        if class_name in target_classes and len(row) > monday_6th_col_idx:
            current_value = row[monday_6th_col_idx]
            # 空白または「欠」以外の場合は「欠」に修正
            if not current_value or current_value != '欠':
                print(f"Fixing {class_name}: '{current_value}' → 欠")
                row[monday_6th_col_idx] = '欠'
                violations_fixed += 1
    
    # 3年6組の月曜6校時も確認（3年3組と同期する必要がある）
    for idx, row in enumerate(data):
        if idx < 2:
            continue
        
        class_name = row[0] if row else ""
        
        if class_name == "3年3組" and len(row) > monday_6th_col_idx:
            parent_value = row[monday_6th_col_idx]
            
            # 3年6組を探して同期
            for ex_idx, ex_row in enumerate(data):
                if ex_idx >= 2 and ex_row and ex_row[0] == "3年6組":
                    if len(ex_row) > monday_6th_col_idx:
                        current_value = ex_row[monday_6th_col_idx]
                        if current_value != parent_value:
                            print(f"Syncing 3年6組: '{current_value}' → {parent_value}")
                            ex_row[monday_6th_col_idx] = parent_value
                            violations_fixed += 1
                    break
            break
    
    # 修正後のデータを保存
    if violations_fixed > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_exchange_monday6th')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Fixed {violations_fixed} exchange class Monday 6th period violations")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("No exchange class Monday 6th period violations found")
    
    return violations_fixed


if __name__ == "__main__":
    violations_fixed = fix_exchange_monday_6th()
    print(f"\nTotal violations fixed: {violations_fixed}")
    print("\n制約違反チェックを再実行してください:")
    print("  python3 scripts/analysis/check_violations.py")