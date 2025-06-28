#!/usr/bin/env python3
"""全ての残りの空きスロットを埋めるスクリプト"""

import pandas as pd
from pathlib import Path

def main():
    # 時間割を読み込む
    df = pd.read_csv("data/output/output.csv", header=None)
    
    print("=== 全ての残りの空きスロットを埋める ===\n")
    
    # 空きスロットの情報（行インデックスは0から）
    empty_slots = [
        # 2年生
        (9, 10, "社"),   # 2年2組 火曜5限 -> 社会
        (13, 10, "社"),  # 2年7組 火曜5限 -> 社会
        
        # 3年生
        (15, 11, "社"),  # 3年1組 火曜6限 -> 社会
        (15, 17, "国"),  # 3年1組 水曜6限 -> 国語
        (16, 5, "国"),   # 3年2組 月曜6限 -> 国語
        (16, 11, "理"),  # 3年2組 火曜6限 -> 理科
        (16, 18, "保"),  # 3年2組 木曜1限 -> 保健体育
        (17, 3, "家"),   # 3年3組 月曜4限 -> 家庭科
        (17, 17, "国"),  # 3年3組 水曜6限 -> 国語
        (19, 3, "英"),   # 3年6組 月曜4限 -> 英語
        (19, 17, "理"),  # 3年6組 水曜6限 -> 理科
        (19, 19, "家"),  # 3年6組 木曜2限 -> 家庭科
        (19, 28, "国"),  # 3年6組 金曜5限 -> 国語
        (20, 5, "保"),   # 3年7組 月曜6限 -> 保健体育
        (20, 11, "理"),  # 3年7組 火曜6限 -> 理科
        (20, 18, "国"),  # 3年7組 木曜1限 -> 国語
    ]
    
    filled = 0
    
    # 各空きスロットを埋める
    for row, col, subject in empty_slots:
        current = df.iloc[row, col]
        current_str = str(current).strip()
        print(f"デバッグ: 行{row}列{col} = '{current}' (型: {type(current).__name__})")
        
        # 空文字列、NaN、空白のいずれかの場合
        if pd.isna(current) or current_str == "" or current_str == "nan" or current_str == "None":
            df.iloc[row, col] = subject
            filled += 1
            
            # クラス名を特定
            class_names = {
                9: "2年2組",
                13: "2年7組",
                15: "3年1組",
                16: "3年2組",
                17: "3年3組",
                19: "3年6組",
                20: "3年7組"
            }
            class_name = class_names.get(row, f"行{row+1}")
            
            # 曜日と時限を特定
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