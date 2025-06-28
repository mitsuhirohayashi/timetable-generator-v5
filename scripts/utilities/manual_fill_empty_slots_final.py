#!/usr/bin/env python3
"""残りの空きスロットを手動で埋めるスクリプト（最終版）"""
import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.domain.entities.schedule import Schedule
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository


def manual_fill_empty_slots():
    """残りの空きスロットを手動で埋める"""
    
    # ファイルパス
    output_path = project_root / "data" / "output" / "output.csv"
    
    # CSVを読み込み
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print("=== 空きスロットの手動埋め込み開始 ===")
    
    # 1. 2年3組 月曜2限を埋める
    # 2年6組が月曜2限に「自立」なので、2年3組は「数」または「英」にする必要がある
    # しかし月曜1限に既に「数」があるので「英」を選択
    print("\n1. 2年3組 月曜2限 -> 英")
    rows[10][2] = "英"  # Row 11 (0-indexed 10), Column 2
    
    # 2. 5組の水曜4限を同期して埋める
    # 5組クラスで不足している教科を確認
    # 国語が適切（全クラスで不足している）
    print("\n2. 5組クラスの水曜4限を同期:")
    print("   - 1年5組 水曜4限 -> 国")
    print("   - 2年5組 水曜4限 -> 国")
    print("   - 3年5組 水曜4限 -> 国")
    
    rows[5][16] = "国"   # 1年5組: Row 6 (0-indexed 5), Column 16
    rows[11][16] = "国"  # 2年5組: Row 12 (0-indexed 11), Column 16
    rows[18][16] = "国"  # 3年5組: Row 19 (0-indexed 18), Column 16
    
    # 3. 3年6組と3年7組の水曜1限を埋める
    print("\n3. 3年交流学級の水曜1限を埋める:")
    print("   - 3年6組 水曜1限 -> 社")
    print("   - 3年7組 水曜1限 -> 理")
    
    rows[19][13] = "社"  # 3年6組: Row 20 (0-indexed 19), Column 13 (水曜1)
    rows[20][13] = "理"  # 3年7組: Row 21 (0-indexed 20), Column 13 (水曜1)
    
    # CSVを保存
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(rows)
    
    print("\n=== 空きスロットの埋め込み完了 ===")
    print(f"更新されたファイル: {output_path}")
    
    # 空きスロット数を確認
    empty_count = 0
    for row_idx, row in enumerate(rows):
        if row_idx < 2:  # ヘッダー行をスキップ
            continue
        if row[0] == "":  # 区切り行をスキップ
            continue
        for col_idx, cell in enumerate(row):
            if col_idx == 0:  # クラス名列をスキップ
                continue
            if cell == "":
                empty_count += 1
                print(f"警告: 空きスロット発見 - 行{row_idx+1}, 列{col_idx+1} ({row[0]})")
    
    if empty_count == 0:
        print("\n✓ すべてのスロットが埋まりました！")
    else:
        print(f"\n⚠ まだ{empty_count}個の空きスロットが残っています")


if __name__ == "__main__":
    manual_fill_empty_slots()