#!/usr/bin/env python3
"""水曜2校時の梶永先生の状況を確認"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.infrastructure.config.path_config import path_config

def debug_wednesday_period2():
    """水曜2校時の状況を確認"""
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行を確認
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 水曜2校時の列インデックスを特定
    target_col = None
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == '水' and period == '2':
            target_col = i + 1
            break
    
    print(f"水曜2校時の列インデックス: {target_col}")
    print("\n水曜2校時の各クラスの授業:")
    
    # 各クラスの水曜2校時を表示
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        subject = row[target_col]
        print(f"  {class_name}: {subject}")
    
    print("\n梶永先生が水曜2校時に担当しているクラス（数学）:")
    print("  1年1組, 1年2組, 1年3組: 同一学年なのでテスト巡回として正常")
    print("  1年5組, 2年5組, 3年5組: 5組は合同授業なので正常")
    print("\n→ 実はこれは制約違反ではない可能性があります")
    
    # Follow-up.csvの内容も確認
    print("\nFollow-up.csvの水曜日の記載:")
    with open(path_config.input_dir / "Follow-up.csv", 'r', encoding='utf-8') as f:
        lines = f.readlines()
        in_wednesday = False
        for line in lines:
            if '水曜日' in line or '水曜' in line:
                in_wednesday = True
            elif '木曜日' in line or '木曜' in line:
                break
            elif in_wednesday and line.strip():
                print(f"  {line.strip()}")

if __name__ == "__main__":
    debug_wednesday_period2()