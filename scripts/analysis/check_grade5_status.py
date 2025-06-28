#!/usr/bin/env python3
"""5組の現在の状況を確認するスクリプト"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv

def check_grade5_status():
    """5組の水曜4限の状況を確認"""
    
    # output.csvを読み込む
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行を取得
    day_row = rows[0]
    period_row = rows[1]
    
    # 水曜4限の列を見つける
    wed4_col = None
    for i, (day, period) in enumerate(zip(day_row, period_row)):
        if day == "水" and period == "4":
            wed4_col = i
            break
    
    if wed4_col is None:
        print("水曜4限が見つかりません")
        return
    
    print("=== 5組の水曜4限の状況 ===")
    
    # 各行を確認
    for row in rows[2:]:
        if len(row) > 0:
            class_name = row[0]
            if "5組" in class_name:
                if wed4_col < len(row):
                    subject = row[wed4_col] if row[wed4_col] else "空き"
                else:
                    subject = "空き"
                print(f"{class_name}: {subject}")
    
    print("\n=== 5組の全体状況 ===")
    # 5組の全データを表示
    for row in rows[2:]:
        if len(row) > 0:
            class_name = row[0]
            if "5組" in class_name:
                print(f"\n{class_name}:")
                for i, (day, period) in enumerate(zip(day_row[1:], period_row[1:])):
                    if i + 1 < len(row):
                        subject = row[i + 1] if row[i + 1] else "空き"
                        print(f"  {day}曜{period}限: {subject}")


if __name__ == "__main__":
    check_grade5_status()