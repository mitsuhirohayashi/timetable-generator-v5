#!/usr/bin/env python3
"""input.csvの内容を完全に尊重してoutput.csvを復元する"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def restore_from_input():
    """input.csvの内容を完全にoutput.csvにコピーする"""
    print("=== input.csvの完全復元 ===")
    print("CLAUDE.mdの原則：固定科目は「保護」するのみで「強制」はしない")
    print("input.csvに入力されている内容を完全に尊重します\n")
    
    # input.csvを読み込む
    input_path = path_config.data_dir / "input" / "input.csv"
    print(f"Reading from: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        input_data = list(reader)
    
    # 現在のoutput.csvを読み込む（構造を保持するため）
    output_path = path_config.output_dir / "output.csv"
    
    # バックアップを作成
    backup_path = output_path.with_suffix('.csv.bak_before_complete_restore')
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        backup_data = list(reader)
    
    with open(backup_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(backup_data)
    print(f"Backup saved to: {backup_path}")
    
    # input.csvの内容をそのままoutput.csvに書き込む
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(input_data)
    
    print(f"\nInput data completely restored to: {output_path}")
    
    # 変更内容のサマリー
    print("\n重要な復元内容:")
    print("1. 全てのYTを保持")
    print("2. 空白は空白のまま保持（固定科目を追加しない）")
    print("3. 道徳（道）を保持")
    print("4. 5組の自立・日生・作業・生単を保持")
    print("5. 交流学級（6組・7組）の空白行を保持")
    
    return True


if __name__ == "__main__":
    success = restore_from_input()
    if success:
        print("\n✅ 復元完了")
        print("\nCLAUDE.mdのルール:")
        print("- システムは固定科目（欠、YT、学、道、学総、総合、行）を勝手に追加してはいけません")
        print("- input.csvに入力されている内容を完全に尊重し、変更しないこと")
        print("- 空白スロットは通常教科（国、数、英、理、社、音、美、保、技、家など）で埋めること")
    else:
        print("\n❌ 復元失敗")