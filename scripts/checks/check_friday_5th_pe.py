#!/usr/bin/env python3
"""金曜5校時の3年6組の状況を確認"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src.infrastructure.config.path_config import path_config

def check_friday_5th_pe():
    """金曜5校時の状況を確認"""
    
    # 時間割を読み込み
    schedule_df = pd.read_csv(path_config.output_dir / "output.csv", header=None)
    
    # ヘッダー行を確認
    days = schedule_df.iloc[0, 1:].tolist()
    periods = schedule_df.iloc[1, 1:].tolist()
    
    # 金曜5校時の列インデックスを特定
    target_col = None
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == '金' and period == '5':
            target_col = i + 1
            break
    
    print("金曜5校時の状況:")
    print("\n体育のクラス:")
    
    # 各クラスの金曜5校時を表示
    pe_classes = []
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if pd.isna(row[0]) or row[0] == "":
            continue
            
        class_name = row[0]
        if '年' not in class_name or '組' not in class_name:
            continue
            
        subject = row[target_col]
        if subject in ['保', '保健', '体育', '保健体育']:
            pe_classes.append(class_name)
            print(f"  {class_name}: {subject}")
    
    print("\n3年6組の金曜5校時:")
    for row_idx in range(2, len(schedule_df)):
        row = schedule_df.iloc[row_idx]
        if row[0] == '3年6組':
            subject = row[target_col]
            print(f"  3年6組: {subject if not pd.isna(subject) else '空き'}")
            
            if subject not in ['保', '保健', '体育', '保健体育']:
                print("\n  → 3年3組が体育なのに、3年6組が体育でない")
                print("  → これは交流学級のルール違反の可能性があります")

if __name__ == "__main__":
    check_friday_5th_pe()