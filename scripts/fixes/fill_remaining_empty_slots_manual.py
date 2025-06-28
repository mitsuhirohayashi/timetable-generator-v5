#!/usr/bin/env python3
"""残りの空きスロットを手動で埋めるスクリプト"""

import pandas as pd
from pathlib import Path

def main():
    # 時間割を読み込む
    df = pd.read_csv("data/output/output.csv", header=None)
    
    print("=== 残りの空きスロットを埋める ===\n")
    
    # 空きスロットの情報（行は0から数える）
    empty_slots = [
        (9, 2, 10, "社"),   # 2年2組(行10) 火曜5限 -> 社会
        (13, 2, 10, "国"),  # 2年7組(行14) 火曜5限 -> 国語
        (15, 3, 11, "保"),  # 3年1組(行16) 火曜6限 -> 保健体育
        (16, 3, 5, "保"),   # 3年2組(行17) 月曜6限 -> 保健体育  
        (16, 3, 11, "国"),  # 3年2組(行17) 火曜6限 -> 国語
        (16, 3, 17, "技"),  # 3年2組(行17) 水曜6限 -> 技術
        (16, 3, 18, "理"),  # 3年2組(行17) 木曜1限 -> 理科
        (17, 3, 3, "家"),   # 3年3組(行18) 月曜4限 -> 家庭科
        (19, 3, 3, "英"),   # 3年6組(行20) 月曜4限 -> 英語
        (19, 3, 19, "理"),  # 3年6組(行20) 木曜2限 -> 理科
        (19, 3, 28, "国"),  # 3年6組(行20) 金曜5限 -> 国語
        (20, 3, 5, "家"),   # 3年7組(行21) 月曜6限 -> 家庭科
        (20, 3, 11, "理"),  # 3年7組(行21) 火曜6限 -> 理科
        (20, 3, 17, "国"),  # 3年7組(行21) 水曜6限 -> 国語
        (20, 3, 18, "数"),  # 3年7組(行21) 木曜1限 -> 数学
    ]
    
    # 各空きスロットを埋める
    for row, header_row, col, subject in empty_slots:
        current = str(df.iloc[row, col]).strip()
        if current == "" or current == "nan":
            df.iloc[row, col] = subject
            
            # クラス名を特定
            if row == 9:
                class_name = "2年2組"
            elif row == 13:
                class_name = "2年7組"
            elif row == 15:
                class_name = "3年1組"
            elif row == 16:
                class_name = "3年2組"
            elif row == 17:
                class_name = "3年3組"
            elif row == 19:
                class_name = "3年6組"
            elif row == 20:
                class_name = "3年7組"
            else:
                class_name = f"行{row+1}"
            
            # 曜日と時限を特定
            day = df.iloc[0, col]
            period = df.iloc[1, col]
            
            print(f"{class_name} {day}曜{period}限に {subject} を配置")
    
    # 結果を保存
    df.to_csv("data/output/output.csv", header=False, index=False)
    print("\n時間割を保存しました。")
    print("完了！")

if __name__ == "__main__":
    main()