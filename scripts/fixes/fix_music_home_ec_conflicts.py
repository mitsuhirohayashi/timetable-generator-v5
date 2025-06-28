#!/usr/bin/env python3
"""
音楽（塚本先生）と家庭科（金子み先生）の教師重複を解決する

問題:
1. 塚本先生: 月曜4限に複数クラスで音楽を同時に教えている
2. 金子み先生: 複数の時間帯で複数クラスを同時に教えている

ルール:
- 音楽: 塚本先生のみが全ての音楽授業を担当
- 家庭科: 金子み先生のみが全ての家庭科授業を担当
- 5組（1-5, 2-5, 3-5）の合同授業は1つの授業としてカウント
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Set

def load_schedule(filepath: str) -> pd.DataFrame:
    """CSVファイルから時間割を読み込む"""
    df = pd.read_csv(filepath, encoding='utf-8')
    return df

def analyze_teacher_conflicts(df: pd.DataFrame, subject: str) -> Dict[Tuple[str, int], List[str]]:
    """特定の科目の時間帯ごとの担当クラスを分析"""
    conflicts = defaultdict(list)
    
    # 時間割の列を処理
    days = ['月', '火', '水', '木', '金']
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            col_idx = day_idx * 6 + period + 1  # +2 because of header columns
            
            for idx, row in df.iterrows():
                if idx < 2:  # Skip header rows
                    continue
                    
                class_name = row.iloc[0]
                if pd.isna(class_name) or class_name == '':
                    continue
                
                if col_idx < len(row):
                    value = row.iloc[col_idx]
                    if pd.notna(value) and value == subject:
                        # 5組の合同授業かチェック
                        if class_name in ['1年5組', '2年5組', '3年5組']:
                            # 5組の合同授業は1つとしてカウント
                            grade5_key = f"5組合同({subject})"
                            if grade5_key not in conflicts[(day, period)]:
                                conflicts[(day, period)].append(grade5_key)
                        else:
                            conflicts[(day, period)].append(class_name)
    
    # 実際の重複のみを返す
    actual_conflicts = {}
    for time_slot, classes in conflicts.items():
        if len(classes) > 1:
            actual_conflicts[time_slot] = classes
    
    return actual_conflicts

def find_available_slots(df: pd.DataFrame, class_name: str, 
                        avoid_subject: str) -> List[Tuple[str, int, int]]:
    """クラスの空き時間を見つける（特定の科目の時間を避ける）"""
    available = []
    
    # Find the row for this class
    class_row = None
    for idx, row in df.iterrows():
        if idx < 2:
            continue
        if row.iloc[0] == class_name:
            class_row = row
            break
    
    if class_row is None:
        return available
    
    days = ['月', '火', '水', '木', '金']
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            col_idx = day_idx * 6 + period + 1
            
            if col_idx < len(class_row):
                value = class_row.iloc[col_idx]
                
                # 空きスロットまたは交換可能な授業
                if pd.isna(value) or value == '' or value not in ['欠', 'YT', '学', '道', '学総', '総', '行', 'テスト', '技家']:
                    # この時間に避けるべき科目が他のクラスで授業していないかチェック
                    teacher_busy = False
                    for idx2, row2 in df.iterrows():
                        if idx2 < 2:
                            continue
                        other_class = row2.iloc[0]
                        if pd.notna(other_class) and other_class != class_name and other_class != '':
                            if col_idx < len(row2):
                                other_value = row2.iloc[col_idx]
                                if pd.notna(other_value) and other_value == avoid_subject:
                                    # 5組合同授業の場合は1つとしてカウント
                                    if other_class in ['1年5組', '2年5組', '3年5組']:
                                        if not teacher_busy:  # まだカウントしていない場合
                                            teacher_busy = True
                                    else:
                                        teacher_busy = True
                                        break
                    
                    if not teacher_busy:
                        available.append((day, period, col_idx))
    
    return available

def swap_subjects(df: pd.DataFrame, class_name: str, 
                 col_idx1: int, col_idx2: int) -> bool:
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
        return False
    
    value1 = df.iloc[class_idx, col_idx1] if col_idx1 < len(df.columns) else None
    value2 = df.iloc[class_idx, col_idx2] if col_idx2 < len(df.columns) else None
    
    # 固定科目は交換しない
    fixed_subjects = {'欠', 'YT', '学', '道', '学総', '総', '行', 'テスト', '技家'}
    if pd.notna(value1) and value1 in fixed_subjects:
        return False
    if pd.notna(value2) and value2 in fixed_subjects:
        return False
    
    # 交換実行
    df.iloc[class_idx, col_idx1] = value2 if pd.notna(value2) else ''
    df.iloc[class_idx, col_idx2] = value1 if pd.notna(value1) else ''
    
    return True

def fix_teacher_conflicts(df: pd.DataFrame, teacher_name: str, subject: str):
    """教師の重複を解決"""
    conflicts = analyze_teacher_conflicts(df, subject)
    
    print(f"\n{teacher_name}先生（{subject}）の重複状況:")
    for (day, period), classes in sorted(conflicts.items()):
        print(f"  {day}曜{period}限: {', '.join(classes)}")
    
    # 各重複時間帯を処理
    for (day, period), conflicting_classes in conflicts.items():
        # 5組合同授業を除外
        actual_classes = [c for c in conflicting_classes if not c.startswith('5組合同')]
        
        if len(actual_classes) <= 1:
            continue  # 実際の重複なし
        
        print(f"\n{day}曜{period}限の重複を解決中...")
        
        # 最初のクラスは残し、他のクラスを移動
        keep_class = actual_classes[0]
        print(f"  {keep_class}は維持")
        
        # 現在の列インデックスを計算
        days = ['月', '火', '水', '木', '金']
        day_idx = days.index(day)
        current_col_idx = day_idx * 6 + period + 1
        
        for move_class in actual_classes[1:]:
            # 移動先を探す
            available_slots = find_available_slots(df, move_class, subject)
            
            # 現在の時間帯と交換可能なスロットを探す
            moved = False
            for target_day, target_period, target_col_idx in available_slots:
                if target_col_idx != current_col_idx:
                    # 交換を試みる
                    if swap_subjects(df, move_class, current_col_idx, target_col_idx):
                        print(f"  {move_class}: {day}曜{period}限 → {target_day}曜{target_period}限")
                        moved = True
                        break
            
            if not moved:
                print(f"  警告: {move_class}の{subject}を移動できませんでした")

def main():
    """メイン処理"""
    # スケジュールを読み込み
    print("スケジュールを読み込み中...")
    df = load_schedule('data/output/output.csv')
    
    # 音楽の担当を確認
    print("\n現在の音楽授業の配置:")
    music_slots = analyze_teacher_conflicts(df, '音')
    all_music_classes = defaultdict(list)
    for (day, period), classes in music_slots.items():
        all_music_classes[(day, period)].extend(classes)
    
    # 音楽の全配置を表示（重複でなくても）
    days = ['月', '火', '水', '木', '金']
    for day in days:
        for period in range(1, 7):
            classes_at_time = []
            for idx, row in df.iterrows():
                if idx < 2:
                    continue
                class_name = row.iloc[0]
                if pd.notna(class_name) and class_name != '':
                    col_idx = days.index(day) * 6 + period + 1
                    if col_idx < len(row):
                        value = row.iloc[col_idx]
                        if pd.notna(value) and value == '音':
                            if class_name in ['1年5組', '2年5組', '3年5組']:
                                if '5組合同(音)' not in classes_at_time:
                                    classes_at_time.append('5組合同(音)')
                            else:
                                classes_at_time.append(class_name)
            
            if classes_at_time:
                print(f"  {day}曜{period}限: {', '.join(classes_at_time)}")
    
    # 塚本先生（音楽）の重複を解決
    print("\n=== 塚本先生（音楽）の重複解決 ===")
    fix_teacher_conflicts(df, '塚本', '音')
    
    # 金子み先生（家庭科）の重複を解決
    print("\n=== 金子み先生（家庭科）の重複解決 ===")
    fix_teacher_conflicts(df, '金子み', '家')
    
    # 修正後の重複を再チェック
    print("\n=== 修正後の確認 ===")
    
    music_conflicts = analyze_teacher_conflicts(df, '音')
    if music_conflicts:
        print(f"\n塚本先生（音楽）の残存重複:")
        for (day, period), classes in sorted(music_conflicts.items()):
            print(f"  {day}曜{period}限: {', '.join(classes)}")
    else:
        print("\n塚本先生（音楽）: 重複解消 ✓")
    
    home_ec_conflicts = analyze_teacher_conflicts(df, '家')
    if home_ec_conflicts:
        print(f"\n金子み先生（家庭科）の残存重複:")
        for (day, period), classes in sorted(home_ec_conflicts.items()):
            print(f"  {day}曜{period}限: {', '.join(classes)}")
    else:
        print("\n金子み先生（家庭科）: 重複解消 ✓")
    
    # 結果を保存
    print("\n修正したスケジュールを保存中...")
    df.to_csv('data/output/output_fixed_music_home_ec.csv', index=False, encoding='utf-8')
    print("修正済みスケジュールを 'data/output/output_fixed_music_home_ec.csv' に保存しました")

if __name__ == "__main__":
    main()