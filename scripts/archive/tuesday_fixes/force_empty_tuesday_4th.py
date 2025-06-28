#!/usr/bin/env python3
"""火曜4限の2年生を強制的に空にする"""

import pandas as pd
from pathlib import Path

def force_empty():
    """火曜4限の2年生を強制的に空にする"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_absolute_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_forced_empty.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜4限の2年生を強制的に空にする ===\n")
    
    def get_cell(day, period):
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(class_name):
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                return i
        return None
    
    tuesday_4th = get_cell("火", "4")
    
    # 2年生クラスの火曜4限を確認して強制移動
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    moved_subjects = []
    
    print("【ステップ1】火曜4限の2年生授業を確認")
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if class_row:
            subject = df.iloc[class_row, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "道徳", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                moved_subjects.append((class_name, class_row, subject))
    
    print(f"\n【ステップ2】{len(moved_subjects)}クラスの授業を他の空きスロットに移動")
    
    for class_name, class_row, subject in moved_subjects:
        # 空きスロットを探す
        moved = False
        
        # まず金曜日を優先的に探す
        for period in ["2", "3", "4", "5"]:
            col = get_cell("金", period)
            if col:
                current = df.iloc[class_row, col]
                if pd.isna(current) or current == "":
                    # 空きスロットに移動
                    df.iloc[class_row, tuesday_4th] = ""
                    df.iloc[class_row, col] = subject
                    print(f"  ✓ {class_name}: {subject} → 金{period}限（空きスロット）")
                    moved = True
                    break
        
        if not moved:
            # 木曜日も探す
            for period in ["2", "3", "4", "5"]:
                col = get_cell("木", period)
                if col:
                    current = df.iloc[class_row, col]
                    if pd.isna(current) or current == "":
                        # 空きスロットに移動
                        df.iloc[class_row, tuesday_4th] = ""
                        df.iloc[class_row, col] = subject
                        print(f"  ✓ {class_name}: {subject} → 木{period}限（空きスロット）")
                        moved = True
                        break
        
        if not moved:
            # 最終手段：任意の非固定科目と交換
            for col in range(1, len(df.columns)):
                if col == tuesday_4th:
                    continue
                day = days[col - 1]
                period = str(periods[col - 1])
                
                # テスト期間と6限は避ける
                if (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or period == "6":
                    continue
                
                current = df.iloc[class_row, col]
                if pd.notna(current) and current not in ["", "欠", "YT", "道", "道徳", "学", "総", "行"]:
                    # 交換
                    df.iloc[class_row, tuesday_4th] = current
                    df.iloc[class_row, col] = subject
                    print(f"  ✓ {class_name}: 火曜4限({subject}) ⇔ {day}{period}限({current})")
                    moved = True
                    break
        
        if not moved:
            print(f"  ✗ {class_name}: 移動先が見つかりません")
    
    # 最終確認
    print("\n【最終確認】火曜4限の2年生クラス:")
    remaining = 0
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if class_row:
            subject = df.iloc[class_row, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "道徳", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                remaining += 1
    
    if remaining == 0:
        print("\n✅ HF会議対応完了！すべての2年生の火曜4限が空になりました")
    else:
        print(f"\n⚠️  まだ{remaining}クラスに授業が残っています")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n最終ファイル: {output_path}")

if __name__ == "__main__":
    force_empty()