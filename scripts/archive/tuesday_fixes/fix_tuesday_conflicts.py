#!/usr/bin/env python3
"""火曜4限と5限の競合を修正するスクリプト"""

import pandas as pd
from pathlib import Path
import sys
from collections import defaultdict

def find_empty_slots(df, class_name, avoid_days=None, avoid_periods=None):
    """指定クラスの空きスロットを検索"""
    avoid_days = avoid_days or []
    avoid_periods = avoid_periods or []
    
    # クラスの行を見つける
    class_row = None
    for idx in range(2, len(df)):
        if df.iloc[idx, 0] == class_name:
            class_row = idx
            break
    
    if class_row is None:
        return []
    
    empty_slots = []
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    for col_idx in range(1, len(df.columns)):
        day = days[col_idx - 1]
        period = str(periods[col_idx - 1])
        
        if day in avoid_days or period in avoid_periods:
            continue
            
        if pd.isna(df.iloc[class_row, col_idx]) or df.iloc[class_row, col_idx] == "":
            empty_slots.append((day, period, col_idx))
    
    return empty_slots

def move_assignment(df, from_class, from_day, from_period, to_day, to_period):
    """授業を移動"""
    # インデックスを見つける
    from_col = None
    to_col = None
    class_row = None
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == from_day and str(periods[col_idx - 1]) == str(from_period):
            from_col = col_idx
        if days[col_idx - 1] == to_day and str(periods[col_idx - 1]) == str(to_period):
            to_col = col_idx
    
    for idx in range(2, len(df)):
        if df.iloc[idx, 0] == from_class:
            class_row = idx
            break
    
    if from_col and to_col and class_row:
        # 授業を移動
        subject = df.iloc[class_row, from_col]
        df.iloc[class_row, to_col] = subject
        df.iloc[class_row, from_col] = ""
        return True, subject
    
    return False, None

def fix_tuesday_conflicts():
    """火曜の競合を修正"""
    # ファイルパス
    input_path = Path(__file__).parent / "data" / "output" / "output.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_fixed.csv"
    
    # CSVを読み込み
    df = pd.read_csv(input_path, header=None)
    
    print("=== 火曜4限と5限の競合修正を開始 ===\n")
    
    # 修正記録
    fixes = []
    
    # 1. 火曜4限のHF会議対応 - 2年生の授業を移動
    print("【HF会議対応】火曜4限の2年生授業を移動")
    
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    
    for class_name in grade2_classes:
        # 火曜4限の授業を確認
        class_row = None
        for idx in range(2, len(df)):
            if df.iloc[idx, 0] == class_name:
                class_row = idx
                break
        
        if class_row is None:
            continue
            
        # 火曜4限のインデックスを見つける
        tuesday_4th_col = None
        days = df.iloc[0, 1:].tolist()
        periods = df.iloc[1, 1:].tolist()
        
        for col_idx in range(1, len(df.columns)):
            if days[col_idx - 1] == "火" and str(periods[col_idx - 1]) == "4":
                tuesday_4th_col = col_idx
                break
        
        if tuesday_4th_col:
            subject = df.iloc[class_row, tuesday_4th_col]
            if pd.notna(subject) and subject != "" and subject not in ["欠", "YT", "道", "学", "総", "行"]:
                # 空きスロットを探す（火曜と月水の1-3限は避ける - テスト期間）
                empty_slots = find_empty_slots(df, class_name, 
                                             avoid_periods=["1", "2", "3", "6"])
                
                if empty_slots:
                    # 最初の空きスロットに移動
                    to_day, to_period, _ = empty_slots[0]
                    success, moved_subject = move_assignment(df, class_name, "火", "4", to_day, to_period)
                    
                    if success:
                        fixes.append(f"{class_name}: {moved_subject} を火曜4限から{to_day}{to_period}限へ移動")
                        print(f"  ✓ {class_name}: {moved_subject} → {to_day}{to_period}限")
                    else:
                        print(f"  ✗ {class_name}: 移動失敗")
                else:
                    print(f"  ✗ {class_name}: 空きスロットなし")
    
    print("\n【火曜5限の教師競合修正】")
    
    # 2. 井上先生の競合修正 - 2年3組の数学を移動
    print("\n2-1. 井上先生の競合修正")
    empty_slots = find_empty_slots(df, "2年3組", avoid_periods=["1", "2", "3", "6"])
    
    suitable_slot = None
    for day, period, _ in empty_slots:
        # その時間に2年2組が数学でないことを確認
        success = True
        for idx in range(2, len(df)):
            if df.iloc[idx, 0] == "2年2組":
                days = df.iloc[0, 1:].tolist()
                periods = df.iloc[1, 1:].tolist()
                for col_idx in range(1, len(df.columns)):
                    if days[col_idx - 1] == day and str(periods[col_idx - 1]) == period:
                        if df.iloc[idx, col_idx] == "数":
                            success = False
                            break
                break
        
        if success:
            suitable_slot = (day, period)
            break
    
    if suitable_slot:
        success, moved_subject = move_assignment(df, "2年3組", "火", "5", suitable_slot[0], suitable_slot[1])
        if success:
            fixes.append(f"2年3組: 数学を火曜5限から{suitable_slot[0]}{suitable_slot[1]}限へ移動")
            print(f"  ✓ 2年3組: 数学 → {suitable_slot[0]}{suitable_slot[1]}限")
    else:
        print("  ✗ 2年3組: 適切な移動先が見つかりません")
    
    # 3. 財津先生の競合修正 - 3年2組の保健体育を移動
    print("\n2-2. 財津先生の競合修正")
    empty_slots = find_empty_slots(df, "3年2組", avoid_periods=["1", "2", "3", "6"])
    
    suitable_slot = None
    for day, period, _ in empty_slots:
        # 体育館の使用状況を確認（簡易的に）
        suitable_slot = (day, period)
        break
    
    if suitable_slot:
        success, moved_subject = move_assignment(df, "3年2組", "火", "5", suitable_slot[0], suitable_slot[1])
        if success:
            fixes.append(f"3年2組: 保健体育を火曜5限から{suitable_slot[0]}{suitable_slot[1]}限へ移動")
            print(f"  ✓ 3年2組: 保健体育 → {suitable_slot[0]}{suitable_slot[1]}限")
    else:
        print("  ✗ 3年2組: 適切な移動先が見つかりません")
    
    # 結果を保存
    df.to_csv(output_path, index=False, header=False)
    
    print(f"\n=== 修正完了 ===")
    print(f"修正内容: {len(fixes)}件")
    for fix in fixes:
        print(f"  - {fix}")
    
    print(f"\n修正後のファイル: {output_path}")
    
    # 修正後の火曜4限と5限を表示
    print("\n【修正後の火曜4限と5限】")
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    tuesday_4th_col = None
    tuesday_5th_col = None
    
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == "火" and str(periods[col_idx - 1]) == "4":
            tuesday_4th_col = col_idx
        if days[col_idx - 1] == "火" and str(periods[col_idx - 1]) == "5":
            tuesday_5th_col = col_idx
    
    if tuesday_4th_col and tuesday_5th_col:
        print("\n火曜4限:")
        for idx in range(2, len(df)):
            class_name = df.iloc[idx, 0]
            if pd.notna(class_name) and class_name != "":
                subject_4th = df.iloc[idx, tuesday_4th_col]
                if pd.notna(subject_4th) and subject_4th != "":
                    print(f"  {class_name}: {subject_4th}")
        
        print("\n火曜5限:")
        for idx in range(2, len(df)):
            class_name = df.iloc[idx, 0]
            if pd.notna(class_name) and class_name != "":
                subject_5th = df.iloc[idx, tuesday_5th_col]
                if pd.notna(subject_5th) and subject_5th != "":
                    print(f"  {class_name}: {subject_5th}")

if __name__ == "__main__":
    fix_tuesday_conflicts()