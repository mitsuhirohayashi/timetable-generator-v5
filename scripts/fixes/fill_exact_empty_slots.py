#!/usr/bin/env python3
"""正確な位置の空きスロットを埋めるスクリプト"""

import pandas as pd
from pathlib import Path

def main():
    # 時間割を読み込む
    df = pd.read_csv("data/output/output.csv", header=None)
    
    print("=== 正確な位置の空きスロットを埋める ===\n")
    
    # 空きスロットの情報（行と列は0ベースインデックス）
    empty_slots = [
        # row, col, subject
        (9, 11, "社"),   # 2年2組 火曜5限
        (13, 11, "社"),  # 2年7組 火曜5限
        (15, 12, "国"),  # 3年1組 火曜6限
        (15, 18, "社"),  # 3年1組 水曜6限
        (16, 6, "国"),   # 3年2組 月曜6限
        (16, 12, "理"),  # 3年2組 火曜6限
        (16, 19, "保"),  # 3年2組 木曜1限
        (17, 4, "家"),   # 3年3組 月曜4限
        (17, 18, "国"),  # 3年3組 水曜6限
        (19, 4, "英"),   # 3年6組 月曜4限
        (19, 18, "理"),  # 3年6組 水曜6限
        (19, 20, "家"),  # 3年6組 木曜2限
        (19, 29, "国"),  # 3年6組 金曜5限
        (20, 6, "保"),   # 3年7組 月曜6限
        (20, 12, "理"),  # 3年7組 火曜6限
        (20, 19, "国"),  # 3年7組 木曜1限
    ]
    
    filled = 0
    
    # 各空きスロットを埋める
    for row, col, subject in empty_slots:
        current = df.iloc[row, col]
        if pd.isna(current) or str(current).strip() == "":
            df.iloc[row, col] = subject
            filled += 1
            
            # クラス名と時間を表示
            class_name = df.iloc[row, 0]
            day = df.iloc[0, col]
            period = df.iloc[1, col]
            
            print(f"{class_name} {day}曜{period}限に {subject} を配置")
    
    # 結果を保存
    df.to_csv("data/output/output.csv", header=False, index=False)
    print(f"\n合計{filled}個の空きスロットを埋めました。")
    print("時間割を保存しました。")
    print("完了！")

if __name__ == "__main__":
    main()