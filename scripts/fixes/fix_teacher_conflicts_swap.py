#!/usr/bin/env python3
"""
教師の重複を科目の入れ替えで解決する

実際の教師-科目-クラスマッピングに基づいて重複を解消
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional
import random

def load_teacher_mapping() -> Dict[Tuple[str, str], str]:
    """教師-科目-クラスのマッピングを読み込む"""
    df = pd.read_csv('data/config/teacher_subject_mapping.csv', encoding='utf-8')
    
    mapping = {}
    for _, row in df.iterrows():
        teacher = row['教員名']
        subject = row['教科']
        grade = row['学年']
        class_num = row['組']
        
        class_name = f"{grade}年{class_num}組"
        mapping[(subject, class_name)] = teacher
    
    return mapping

def load_schedule(filepath: str) -> pd.DataFrame:
    """CSVファイルから時間割を読み込む"""
    df = pd.read_csv(filepath, encoding='utf-8')
    return df

def get_teacher_schedule(df: pd.DataFrame, teacher_mapping: Dict[Tuple[str, str], str]) -> Dict[str, Dict[Tuple[str, int], List[Tuple[str, str]]]]:
    """教師ごとのスケジュールを取得"""
    teacher_schedule = defaultdict(lambda: defaultdict(list))
    
    days = ['月', '火', '水', '木', '金']
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            col_idx = day_idx * 6 + period + 1
            
            for idx, row in df.iterrows():
                if idx < 2:
                    continue
                    
                class_name = row.iloc[0]
                if pd.isna(class_name) or class_name == '':
                    continue
                
                if col_idx < len(row):
                    subject = row.iloc[col_idx]
                    if pd.notna(subject) and subject != '':
                        teacher = teacher_mapping.get((subject, class_name), None)
                        
                        if teacher:
                            # 5組の合同授業は特別扱い
                            if class_name in ['1年5組', '2年5組', '3年5組']:
                                # 既に5組合同として登録されているか確認
                                grade5_entry = None
                                for entry in teacher_schedule[teacher][(day, period)]:
                                    if entry[0].startswith('5組合同'):
                                        grade5_entry = entry
                                        break
                                
                                if not grade5_entry:
                                    teacher_schedule[teacher][(day, period)].append((f'5組合同', subject))
                            else:
                                teacher_schedule[teacher][(day, period)].append((class_name, subject))
    
    return teacher_schedule

def find_conflicts(teacher_schedule: Dict[str, Dict[Tuple[str, int], List[Tuple[str, str]]]]) -> Dict[str, List[Tuple[Tuple[str, int], List[Tuple[str, str]]]]]:
    """重複を見つける"""
    conflicts = {}
    
    for teacher, schedule in teacher_schedule.items():
        teacher_conflicts = []
        for time_slot, assignments in schedule.items():
            if len(assignments) > 1:
                teacher_conflicts.append((time_slot, assignments))
        
        if teacher_conflicts:
            conflicts[teacher] = teacher_conflicts
    
    return conflicts

def can_swap(df: pd.DataFrame, class_name: str, col_idx1: int, col_idx2: int) -> bool:
    """2つの時間帯の授業が交換可能かチェック"""
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
    
    # 少なくとも一方に値があれば交換可能
    return True

def perform_swap(df: pd.DataFrame, class_name: str, col_idx1: int, col_idx2: int):
    """実際に交換を実行"""
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

def resolve_conflict(df: pd.DataFrame, teacher: str, time_slot: Tuple[str, int], 
                    assignments: List[Tuple[str, str]], 
                    teacher_mapping: Dict[Tuple[str, str], str],
                    teacher_schedule: Dict[str, Dict[Tuple[str, int], List[Tuple[str, str]]]]) -> bool:
    """1つの重複を解決"""
    day, period = time_slot
    days = ['月', '火', '水', '木', '金']
    conflict_col_idx = days.index(day) * 6 + period + 1
    
    # 5組合同を除いた実際のクラス
    actual_assignments = [a for a in assignments if not a[0].startswith('5組合同')]
    
    if len(actual_assignments) <= 1:
        return True  # 実質的な重複なし
    
    # 最初のクラスは残し、他を移動
    keep_assignment = actual_assignments[0]
    
    for move_assignment in actual_assignments[1:]:
        class_name, subject = move_assignment
        moved = False
        
        # 他の時間帯を探す
        for target_day_idx, target_day in enumerate(days):
            for target_period in range(1, 7):
                if (target_day, target_period) == time_slot:
                    continue
                
                target_col_idx = target_day_idx * 6 + target_period + 1
                
                # 交換可能かチェック
                if can_swap(df, class_name, conflict_col_idx, target_col_idx):
                    # 交換後の教師スケジュールをシミュレート
                    # 現在の値を取得
                    class_idx = None
                    for idx, row in df.iterrows():
                        if idx < 2:
                            continue
                        if row.iloc[0] == class_name:
                            class_idx = idx
                            break
                    
                    if class_idx is not None:
                        current_subject = df.iloc[class_idx, conflict_col_idx] if conflict_col_idx < len(df.columns) else None
                        target_subject = df.iloc[class_idx, target_col_idx] if target_col_idx < len(df.columns) else None
                        
                        # 交換後に新たな重複が発生しないかチェック
                        conflict_free = True
                        
                        # 移動先に教師が既にいないかチェック
                        if pd.notna(current_subject) and current_subject != '':
                            current_teacher = teacher_mapping.get((current_subject, class_name), None)
                            if current_teacher and current_teacher in teacher_schedule:
                                if len(teacher_schedule[current_teacher].get((target_day, target_period), [])) > 0:
                                    # 5組合同の場合は許可
                                    other_assignments = teacher_schedule[current_teacher].get((target_day, target_period), [])
                                    non_grade5 = [a for a in other_assignments if not a[0].startswith('5組合同')]
                                    if non_grade5:
                                        conflict_free = False
                        
                        if conflict_free:
                            # 交換を実行
                            perform_swap(df, class_name, conflict_col_idx, target_col_idx)
                            print(f"  {class_name}: {subject}を{day}曜{period}限から{target_day}曜{target_period}限へ移動")
                            moved = True
                            
                            # teacher_scheduleを更新
                            teacher_schedule[teacher][(day, period)] = [a for a in teacher_schedule[teacher][(day, period)] if a != move_assignment]
                            teacher_schedule[teacher][(target_day, target_period)].append(move_assignment)
                            break
            
            if moved:
                break
        
        if not moved:
            print(f"  警告: {class_name}の{subject}（{teacher}先生）を移動できませんでした")
            return False
    
    return True

def main():
    """メイン処理"""
    # 教師マッピングを読み込み
    print("教師-科目-クラスのマッピングを読み込み中...")
    teacher_mapping = load_teacher_mapping()
    
    # スケジュールを読み込み  
    print("スケジュールを読み込み中...")
    df = load_schedule('data/output/output.csv')
    
    # 教師スケジュールを構築
    teacher_schedule = get_teacher_schedule(df, teacher_mapping)
    
    # 重複を見つける
    conflicts = find_conflicts(teacher_schedule)
    
    if not conflicts:
        print("\n教師の重複はありません！")
        return
    
    print(f"\n重複がある教師数: {len(conflicts)}")
    
    # 各教師の重複を解決
    for teacher in sorted(conflicts.keys()):
        print(f"\n{teacher}先生の重複を解決中:")
        
        for time_slot, assignments in conflicts[teacher]:
            day, period = time_slot
            print(f"  {day}曜{period}限: {', '.join([f'{a[0]}({a[1]})' for a in assignments])}")
            
            # 重複を解決
            if not resolve_conflict(df, teacher, time_slot, assignments, teacher_mapping, teacher_schedule):
                print(f"    → 一部解決できませんでした")
    
    # 再度教師スケジュールを構築して確認
    print("\n=== 修正後の確認 ===")
    teacher_schedule_after = get_teacher_schedule(df, teacher_mapping)
    conflicts_after = find_conflicts(teacher_schedule_after)
    
    if not conflicts_after:
        print("全ての教師重複が解消されました！ ✓")
    else:
        print(f"\n残存する重複: {len(conflicts_after)}件")
        for teacher in sorted(conflicts_after.keys()):
            print(f"\n{teacher}先生:")
            for time_slot, assignments in conflicts_after[teacher]:
                day, period = time_slot
                print(f"  {day}曜{period}限: {', '.join([f'{a[0]}({a[1]})' for a in assignments])}")
    
    # 結果を保存
    print("\n修正したスケジュールを保存中...")
    df.to_csv('data/output/output_fixed_teacher_conflicts.csv', index=False, encoding='utf-8')
    print("修正済みスケジュールを 'data/output/output_fixed_teacher_conflicts.csv' に保存しました")

if __name__ == "__main__":
    main()