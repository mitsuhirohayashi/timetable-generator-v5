#!/usr/bin/env python3
"""初期スケジュールの詳細チェック"""

import pandas as pd

def check_initial_schedule():
    """初期スケジュールの詳細を確認"""
    print("=== 初期スケジュール（input.csv）の詳細分析 ===\n")
    
    # CSVを読み込む
    df = pd.read_csv("data/input/input.csv", header=None)
    
    # クラスごとの空きコマ数を計算
    empty_by_class = {}
    for i in range(df.shape[0]):
        class_name = str(df.iloc[i, 0]).strip()
        if pd.isna(class_name) or class_name == "基本時間割":
            continue
        
        empty_count = 0
        for j in range(1, df.shape[1]):
            cell = df.iloc[i, j]
            if pd.isna(cell) or str(cell).strip() == "":
                empty_count += 1
        
        empty_by_class[class_name] = empty_count
    
    print("【クラスごとの空きコマ数】")
    total_empty = 0
    for class_name, count in sorted(empty_by_class.items()):
        print(f"{class_name}: {count}コマ空き")
        total_empty += count
    
    print(f"\n総空きコマ数: {total_empty}")
    
    # 交流学級の自立活動をチェック
    print("\n【交流学級の詳細】")
    exchange_classes = ["1-6", "1-7", "2-6", "2-7", "3-6", "3-7"]
    
    for i in range(df.shape[0]):
        class_name = str(df.iloc[i, 0]).strip()
        if class_name in exchange_classes:
            print(f"\n{class_name}の時間割:")
            days = ["月", "火", "水", "木", "金"]
            periods = ["1", "2", "3", "4", "5", "6"]
            
            for day_idx, day in enumerate(days):
                line = f"  {day}: "
                for period_idx in range(6):
                    col_idx = day_idx * 6 + period_idx + 1
                    if col_idx < df.shape[1]:
                        cell = df.iloc[i, col_idx]
                        if pd.isna(cell) or str(cell).strip() == "":
                            line += "[空] "
                        else:
                            line += f"{cell} "
                print(line)
    
    # 5組の詳細
    print("\n【5組の詳細】")
    grade5_classes = ["1-5", "2-5", "3-5"]
    
    for i in range(df.shape[0]):
        class_name = str(df.iloc[i, 0]).strip()
        if class_name in grade5_classes:
            print(f"\n{class_name}の時間割:")
            days = ["月", "火", "水", "木", "金"]
            
            for day_idx, day in enumerate(days):
                line = f"  {day}: "
                for period_idx in range(6):
                    col_idx = day_idx * 6 + period_idx + 1
                    if col_idx < df.shape[1]:
                        cell = df.iloc[i, col_idx]
                        if pd.isna(cell) or str(cell).strip() == "":
                            line += "[空] "
                        else:
                            line += f"{cell} "
                print(line)

if __name__ == "__main__":
    check_initial_schedule()