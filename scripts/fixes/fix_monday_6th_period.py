#!/usr/bin/env python3
"""月曜6校時の制約違反を修正（1・2年生は「欠」にする）"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def fix_monday_6th_period():
    """月曜6校時の制約違反を修正（1・2年生は「欠」にする）"""
    print("=== 月曜6校時の制約違反を修正 ===")
    print("1・2年生の月曜6校時を「欠」に変更します\n")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 月曜6校時の列インデックス（0-indexed）
    # 月曜1-6校時は列1-6
    monday_6th_col_idx = 6
    
    # 各行を処理
    violations_fixed = 0
    for idx, row in enumerate(data):
        if idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
            
        # クラス名から学年を抽出
        if '年' in class_name:
            try:
                grade = int(class_name.split('年')[0])
                
                # 1年生と2年生の月曜6校時を「欠」に修正
                if grade in [1, 2] and len(row) > monday_6th_col_idx:
                    current_value = row[monday_6th_col_idx]
                    if current_value and current_value != '欠':
                        print(f"Fixing {class_name}: {current_value} → 欠")
                        row[monday_6th_col_idx] = '欠'
                        violations_fixed += 1
            except (ValueError, IndexError):
                continue
    
    # 修正後のデータを保存
    if violations_fixed > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_monday6th')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"Fixed {violations_fixed} Monday 6th period violations")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("No Monday 6th period violations found")
    
    return violations_fixed


if __name__ == "__main__":
    violations_fixed = fix_monday_6th_period()
    print(f"\nTotal violations fixed: {violations_fixed}")
    print("\n制約違反チェックを再実行してください:")
    print("  python3 check_violations.py")