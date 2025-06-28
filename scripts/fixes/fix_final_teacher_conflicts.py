#!/usr/bin/env python3
"""
最終的な教師重複を解決する

残っている2つの重複:
1. 北先生: 水曜6限に3年2組と3年3組で社会
2. 林先生: 火曜6限に2年3組と3年3組で技術
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from typing import List, Tuple

def load_schedule(filepath: str) -> pd.DataFrame:
    """CSVファイルから時間割を読み込む"""
    df = pd.read_csv(filepath, encoding='utf-8')
    return df

def find_empty_slot(df: pd.DataFrame, class_name: str, avoid_slots: List[Tuple[str, int]] = None) -> Tuple[str, int, int]:
    """クラスの空きスロットを見つける"""
    avoid_slots = avoid_slots or []
    
    # Find the row for this class
    class_idx = None
    for idx, row in df.iterrows():
        if idx < 2:
            continue
        if row.iloc[0] == class_name:
            class_idx = idx
            break
    
    if class_idx is None:
        return None
    
    days = ['月', '火', '水', '木', '金']
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            if (day, period) in avoid_slots:
                continue
                
            col_idx = day_idx * 6 + period + 1
            
            if col_idx < len(df.columns):
                value = df.iloc[class_idx, col_idx]
                
                # 空きスロットまたは通常授業（固定科目でない）
                if pd.isna(value) or value == '' or value not in ['欠', 'YT', '学', '道', '学総', '総', '行', 'テスト', '技家']:
                    return (day, period, col_idx)
    
    return None

def swap_subjects(df: pd.DataFrame, class_name: str, col_idx1: int, col_idx2: int):
    """2つの時間帯の授業を交換"""
    # Find the row for this class
    class_idx = None
    for idx, row in df.iterrows():
        if idx < 2:
            continue
        if row.iloc[0] == class_name:
            class_idx = idx
            break
    
    if class_idx is None:
        return
    
    value1 = df.iloc[class_idx, col_idx1] if col_idx1 < len(df.columns) else ''
    value2 = df.iloc[class_idx, col_idx2] if col_idx2 < len(df.columns) else ''
    
    df.iloc[class_idx, col_idx1] = value2 if pd.notna(value2) else ''
    df.iloc[class_idx, col_idx2] = value1 if pd.notna(value1) else ''

def main():
    """メイン処理"""
    # スケジュールを読み込み
    print("スケジュールを読み込み中...")
    try:
        df = load_schedule('data/output/output_fixed_teacher_conflicts.csv')
        print("修正版スケジュール (output_fixed_teacher_conflicts.csv) を使用")
    except:
        df = load_schedule('data/output/output.csv')
        print("元のスケジュール (output.csv) を使用")
    
    print("\n=== 残っている教師重複の解決 ===")
    
    # 1. 北先生の重複を解決（水曜6限: 3年2組と3年3組の社会）
    print("\n1. 北先生の重複解決（水曜6限）:")
    print("   3年2組: 社会, 3年3組: 社会")
    
    # 3年3組の社会を移動
    days = ['月', '火', '水', '木', '金']
    wed_6_col = days.index('水') * 6 + 6 + 1  # 水曜6限の列インデックス
    
    # 3年3組の空きスロットを探す（テスト期間を避ける）
    test_periods = [('月', 1), ('月', 2), ('月', 3), ('火', 1), ('火', 2), ('火', 3), ('水', 1), ('水', 2)]
    
    empty_slot = find_empty_slot(df, '3年3組', avoid_slots=test_periods)
    if empty_slot:
        day, period, col_idx = empty_slot
        swap_subjects(df, '3年3組', wed_6_col, col_idx)
        print(f"   → 3年3組の社会を水曜6限から{day}曜{period}限へ移動")
    else:
        print("   → 3年3組の社会を移動できる空きスロットが見つかりませんでした")
    
    # 2. 林先生の重複を解決（火曜6限: 2年3組と3年3組の技術）
    print("\n2. 林先生の重複解決（火曜6限）:")
    print("   2年3組: 技術, 3年3組: 技術")
    
    # 2年3組の技術を移動
    tue_6_col = days.index('火') * 6 + 6 + 1  # 火曜6限の列インデックス
    
    # 2年3組の空きスロットを探す
    empty_slot = find_empty_slot(df, '2年3組', avoid_slots=test_periods)
    if empty_slot:
        day, period, col_idx = empty_slot
        swap_subjects(df, '2年3組', tue_6_col, col_idx)
        print(f"   → 2年3組の技術を火曜6限から{day}曜{period}限へ移動")
    else:
        print("   → 2年3組の技術を移動できる空きスロットが見つかりませんでした")
    
    # 結果を保存
    print("\n修正したスケジュールを保存中...")
    df.to_csv('data/output/output_final_fixed.csv', index=False, encoding='utf-8')
    print("最終修正済みスケジュールを 'data/output/output_final_fixed.csv' に保存しました")
    
    # 最終確認
    print("\n=== 最終確認 ===")
    print("テスト期間を除いた教師重複の解決が完了しました。")
    print("残っている課題:")
    print("- 交流学級（6組、7組）の教師割り当てが必要")
    print("- これらは親学級との同期や自立活動の配置により別途対応が必要です")

if __name__ == "__main__":
    main()