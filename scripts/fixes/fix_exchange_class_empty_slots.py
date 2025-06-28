#!/usr/bin/env python3
"""
交流学級の空きスロットを親学級に合わせて埋める
"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def fix_exchange_empty_slots():
    """交流学級の空きスロットを修正"""
    
    # 交流学級と親学級の対応
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    # CSVファイルを読み込む
    input_path = project_root / 'data' / 'output' / 'output.csv'
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # クラスごとの行を見つける
    class_rows = {}
    for idx, row in enumerate(rows):
        if row and row[0] in exchange_pairs:
            class_rows[row[0]] = idx
        elif row and row[0] in exchange_pairs.values():
            class_rows[row[0]] = idx
    
    # 修正カウンター
    fixed_count = 0
    
    # 交流学級の空きスロットを埋める
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in class_rows or parent_class not in class_rows:
            continue
        
        exchange_idx = class_rows[exchange_class]
        parent_idx = class_rows[parent_class]
        
        # 各時間をチェック（1-30列が月1〜金6）
        for col_idx in range(1, 31):
            if col_idx < len(rows[exchange_idx]) and col_idx < len(rows[parent_idx]):
                exchange_subj = rows[exchange_idx][col_idx].strip()
                parent_subj = rows[parent_idx][col_idx].strip()
                
                # 交流学級が空きで、親学級に授業がある場合
                if not exchange_subj and parent_subj and exchange_subj != '自立':
                    rows[exchange_idx][col_idx] = parent_subj
                    day = ['月', '火', '水', '木', '金'][(col_idx-1)//6]
                    period = ((col_idx-1) % 6) + 1
                    print(f"修正: {exchange_class} {day}曜{period}限 → {parent_subj} (親学級: {parent_class})")
                    fixed_count += 1
    
    # ファイルに書き出す
    output_path = project_root / 'data' / 'output' / 'output_exchange_fixed.csv'
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"\n合計 {fixed_count} 個の空きスロットを修正しました")
    print(f"結果を {output_path} に保存しました")
    
    # 元のファイルを置き換える
    import shutil
    shutil.copy(output_path, input_path)
    print(f"元のファイル {input_path} を更新しました")

if __name__ == '__main__':
    fix_exchange_empty_slots()