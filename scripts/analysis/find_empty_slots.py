#!/usr/bin/env python3
"""空きスロットを正確に見つけるスクリプト"""

import pandas as pd
from pathlib import Path

def main():
    # 時間割を読み込む
    df = pd.read_csv("data/output/output.csv", header=None)
    
    print("=== 空きスロットを検索 ===\n")
    
    empty_slots = []
    
    # 行3から21まで（実際のクラスデータ）をチェック
    for row_idx in range(2, len(df)):
        row = df.iloc[row_idx]
        
        # 空白行（15行目）はスキップ
        if pd.isna(row[0]) or str(row[0]).strip() == "":
            continue
            
        class_name = row[0]
        
        # 各列（時間割）をチェック
        for col_idx in range(1, len(row)):
            value = row[col_idx]
            
            # 空きスロットかチェック
            if pd.isna(value) or str(value).strip() == "":
                day = df.iloc[0, col_idx]
                period = df.iloc[1, col_idx]
                empty_slots.append({
                    'row': row_idx,
                    'col': col_idx,
                    'class': class_name,
                    'day': day,
                    'period': period
                })
    
    # 結果を表示
    print(f"見つかった空きスロット: {len(empty_slots)}個\n")
    
    for slot in empty_slots:
        print(f"行{slot['row']+1} 列{slot['col']+1}: {slot['class']} {slot['day']}曜{slot['period']}限")
    
    # クラス別に集計
    print("\n【クラス別集計】")
    class_counts = {}
    for slot in empty_slots:
        class_name = slot['class']
        if class_name not in class_counts:
            class_counts[class_name] = 0
        class_counts[class_name] += 1
    
    for class_name, count in sorted(class_counts.items()):
        print(f"{class_name}: {count}個")

if __name__ == "__main__":
    main()