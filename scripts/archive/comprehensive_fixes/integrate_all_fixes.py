#!/usr/bin/env python3
"""すべての修正を統合するスクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import shutil

def integrate_fixes():
    """火曜日修正と会議時間修正を統合"""
    
    # まず会議修正済みファイルをコピー
    meetings_fixed = Path(__file__).parent / "data" / "output" / "output_meetings_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_all_fixed.csv"
    
    # 火曜日修正済みファイルから火曜日のデータを取得
    tuesday_fixed = Path(__file__).parent / "data" / "output" / "output_final_resolved.csv"
    
    if not tuesday_fixed.exists():
        print("火曜日修正済みファイルが見つかりません")
        return
    
    # 両方のファイルを読み込み
    df_meetings = pd.read_csv(meetings_fixed, header=None)
    df_tuesday = pd.read_csv(tuesday_fixed, header=None)
    
    days = df_meetings.iloc[0, 1:].tolist()
    periods = df_meetings.iloc[1, 1:].tolist()
    
    print("=== すべての修正を統合 ===\n")
    
    # 火曜日の列インデックスを取得
    tuesday_cols = []
    for i, day in enumerate(days):
        if day == "火":
            tuesday_cols.append(i + 1)
    
    print(f"火曜日の列: {tuesday_cols}")
    
    # 火曜日のデータを会議修正済みファイルに上書き
    for col in tuesday_cols:
        for row in range(2, len(df_meetings)):
            if row < len(df_tuesday):
                df_meetings.iloc[row, col] = df_tuesday.iloc[row, col]
    
    # 保存
    df_meetings.to_csv(output_path, index=False, header=False)
    print(f"\n統合完了: {output_path}")
    
    # 検証
    print("\n【統合結果の検証】")
    
    # 火曜4限の2年生チェック
    print("\n火曜4限の2年生:")
    tuesday_4th = None
    for i, (d, p) in enumerate(zip(days, periods)):
        if d == "火" and str(p) == "4":
            tuesday_4th = i + 1
            break
    
    if tuesday_4th:
        grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
        for i in range(2, len(df_meetings)):
            class_name = df_meetings.iloc[i, 0]
            if class_name in grade2_classes:
                subject = df_meetings.iloc[i, tuesday_4th]
                print(f"  {class_name}: {subject}")
    
    # 月曜4限（特会）チェック
    print("\n月曜4限（特会）の該当クラス:")
    monday_4th = None
    for i, (d, p) in enumerate(zip(days, periods)):
        if d == "月" and str(p) == "4":
            monday_4th = i + 1
            break
    
    if monday_4th:
        check_classes = ["1年3組", "2年2組", "2年3組", "3年2組"]
        for i in range(2, len(df_meetings)):
            class_name = df_meetings.iloc[i, 0]
            if class_name in check_classes:
                subject = df_meetings.iloc[i, monday_4th]
                print(f"  {class_name}: {subject}")

if __name__ == "__main__":
    integrate_fixes()