#!/usr/bin/env python3
"""シンプルな空きスロット埋めスクリプト"""

import sys
from pathlib import Path
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=== シンプルな空きスロット埋めを開始 ===\n")
    
    # CSVファイルを直接操作
    input_file = project_root / "data" / "output" / "output.csv"
    output_file = project_root / "data" / "output" / "output_fixed.csv"
    
    # CSVファイルを読み込み
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    if len(lines) < 3:
        logger.error("CSVファイルの形式が正しくありません")
        return
    
    # ヘッダー行を保持
    header_lines = lines[:2]
    
    # データ行を処理
    data_lines = []
    filled_count = 0
    
    # 画像から特定された空きスロット（行番号と列番号）
    empty_slots = {
        # 1年6組（行7）
        (7, 5): "理",   # 月5限
        (7, 24): "国",  # 木6限
        (7, 29): "社",  # 金5限
        
        # 1年7組（行8）
        (8, 4): "数",   # 月4限
        (8, 24): "社",  # 木6限
        (8, 28): "国",  # 金4限
        (8, 30): "理",  # 金6限
        
        # 2年6組（行13）
        (13, 14): "国", # 水2限
        (13, 22): "英", # 木4限
        (13, 24): "理", # 木6限
        (13, 30): "数", # 金6限
        
        # 2年7組（行14）
        (14, 9): "数",  # 火3限
        (14, 24): "社", # 木6限
        (14, 25): "国", # 金1限
        (14, 28): "英", # 金4限
        (14, 29): "理", # 金5限
        (14, 30): "社", # 金6限
        
        # 3年6組（行20）
        (20, 17): "数", # 水5限
        (20, 23): "国", # 木5限
        (20, 26): "社", # 金2限
        (20, 28): "英", # 金4限
        (20, 30): "理", # 金6限
        
        # 3年7組（行21）
        (21, 16): "理", # 水4限
        (21, 28): "数", # 金4限
        (21, 30): "国", # 金6限
    }
    
    # 各行を処理
    for i, line in enumerate(lines[2:], start=3):  # 3行目から開始（1-indexed）
        if not line.strip():
            data_lines.append(line)
            continue
        
        fields = line.strip().split(',')
        
        # 空きスロットを埋める
        for (row, col), subject in empty_slots.items():
            if i == row and col < len(fields):
                if not fields[col] or fields[col].strip() == "":
                    fields[col] = subject
                    filled_count += 1
                    logger.info(f"✓ {fields[0]} 列{col}: {subject}を配置")
        
        data_lines.append(','.join(fields) + '\n')
    
    # 結果を保存
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(header_lines)
        f.writelines(data_lines)
    
    logger.info(f"\n合計 {filled_count}個の空きスロットを埋めました")
    logger.info(f"結果を保存: {output_file}")
    
    # 元のファイルにコピー
    import shutil
    shutil.copy(output_file, input_file)
    logger.info(f"元のファイルを更新: {input_file}")


if __name__ == "__main__":
    main()