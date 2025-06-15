#!/usr/bin/env python3
"""
2年7組の後に空白行を追加するスクリプト
"""

import csv
from pathlib import Path
import shutil
import datetime
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def add_blank_line_after_2_7():
    """2年7組の後に空白行を追加"""
    base_dir = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5")
    input_file = base_dir / "data" / "output" / "output.csv"
    
    # バックアップ作成
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = base_dir / "data" / "output" / f"output_backup_{timestamp}.csv"
    shutil.copy(input_file, backup_file)
    logger.info(f"バックアップを作成: {backup_file}")
    
    # CSVを読み込む
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # 新しい行リストを作成
    new_rows = []
    for i, row in enumerate(rows):
        new_rows.append(row)
        # 2年7組の後に空白行を追加
        if len(row) > 0 and row[0] == '2年7組':
            # 空白行（最初のセルは空、残りも空）
            blank_row = [''] + [''] * 30
            new_rows.append(blank_row)
            logger.info("2年7組の後に空白行を追加しました")
    
    # CSVに書き戻す
    with open(input_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for row in new_rows:
            writer.writerow(row)
    
    logger.info(f"更新済み時間割を保存: {input_file}")

if __name__ == "__main__":
    add_blank_line_after_2_7()