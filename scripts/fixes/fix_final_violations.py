#!/usr/bin/env python3
"""最終的な制約違反を修正するスクリプト（リファクタリング版）"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from collections import Counter
from src.application.services.script_utilities import script_utils

def fix_teacher_conflict(df):
    """教師の重複を修正（白石先生の火曜5限）"""
    print("=== 教師重複の修正 ===")
    
    try:
        # 3年1組と3年3組の火曜5限を確認
        _, _, class31_tue5 = script_utils.get_schedule_cell(df, "3年1組", "火", 5)
        _, _, class33_tue5 = script_utils.get_schedule_cell(df, "3年3組", "火", 5)
        
        # 両方とも理科の場合、3年3組を英語に変更
        if class31_tue5 == "理" and class33_tue5 == "理":
            script_utils.set_schedule_cell(df, "3年3組", "火", 5, "英")
            print("3年3組の火曜5限を理→英に変更")
    except ValueError as e:
        print(f"Error: {e}")

def fix_daily_duplicates(df):
    """日内重複を修正"""
    print("\n=== 日内重複の修正 ===")
    
    # 重複をチェック
    violations = script_utils.check_daily_duplicates(df)
    
    # 各違反を修正
    for violation in violations:
        class_name = violation['class']
        day = violation['day']
        subject = violation['subject']
        periods = violation['periods']
        
        print(f"{class_name}の{day}曜日: {subject}が{periods}に重複")
        
        # 2回目の出現を別の科目に変更
        alt_subject = find_alternative_subject(df, class_name, subject)
        if alt_subject:
            script_utils.set_schedule_cell(df, class_name, day, periods[1], alt_subject)
            print(f"  {day}曜{periods[1]}限: {subject} → {alt_subject}")

def find_alternative_subject(df, class_name, exclude_subject):
    """代替科目を見つける"""
    # 標準時数を取得
    base_hours = get_class_base_hours(class_name)
    
    # 現在の科目数をカウント
    current_counts = Counter()
    class_row = None
    for i in range(2, len(df)):
        if df.iloc[i, 0] == class_name:
            class_row = i
            break
    
    if class_row is not None:
        for cell in df.iloc[class_row, 1:]:
            cell_str = str(cell) if pd.notna(cell) else ""
            if cell_str and not script_utils.is_fixed_subject(cell_str):
                current_counts[cell_str] += 1
    
    # 不足している科目を優先
    candidates = []
    for subject, target in base_hours.items():
        if subject != exclude_subject and not script_utils.is_fixed_subject(subject):
            current = current_counts.get(subject, 0)
            if current < target:
                candidates.append((subject, target - current))
    
    # 不足が多い順にソート
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    if candidates:
        return candidates[0][0]
    
    # 見つからない場合は主要科目から選択
    main_subjects = ["国", "数", "英", "理", "社"]
    for subject in main_subjects:
        if subject != exclude_subject:
            return subject
    
    return None

def get_class_base_hours(class_name):
    """特定クラスの標準時数を取得"""
    import csv
    base_hours = {}
    
    with open(script_utils.path_config.base_timetable_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から科目を取得
    subjects = [cell.strip() for cell in rows[1][1:] if cell.strip()]
    
    # 該当クラスの標準時数を取得
    for row in rows[2:]:
        if len(row) > 0 and row[0] == class_name:
            for i, subject in enumerate(subjects):
                if i + 1 < len(row) and row[i + 1]:
                    try:
                        hours = float(row[i + 1])
                        if hours > 0:
                            base_hours[subject] = hours
                    except ValueError:
                        pass
            break
    
    return base_hours

def fix_gym_conflict(df):
    """体育館使用の重複を修正（月曜4限）"""
    print("\n=== 体育館使用の修正 ===")
    
    # 月曜4限に保健体育があるクラスを確認
    pe_classes = []
    for row_idx in range(2, len(df)):
        row = df.iloc[row_idx]
        if pd.isna(row[0]) or str(row[0]).strip() == "":
            continue
        
        class_name = row[0]
        try:
            _, _, subject = script_utils.get_schedule_cell(df, class_name, "月", 4)
            if subject == "保":
                pe_classes.append(class_name)
        except ValueError:
            continue
    
    print(f"月曜4限に保健体育: {pe_classes}")
    
    # 2年1組以外の体育を別の科目に変更
    for class_name in pe_classes:
        if class_name != "2年1組":
            alt_subject = find_alternative_subject(df, class_name, "保")
            if alt_subject:
                script_utils.set_schedule_cell(df, class_name, "月", 4, alt_subject)
                print(f"{class_name}の月曜4限: 保 → {alt_subject}")

def fill_remaining_empty(df):
    """残りの空きコマを埋める"""
    print("\n=== 残りの空きコマを埋める ===")
    
    # 空きスロットを見つける
    empty_slots = script_utils.find_empty_slots(df)
    
    filled = 0
    for slot in empty_slots:
        class_name = slot['class']
        alt_subject = find_alternative_subject(df, class_name, "")
        if alt_subject:
            df.iloc[slot['row'], slot['col']] = alt_subject
            filled += 1
            print(f"{class_name}の{slot['day']}曜{slot['period']}限 → {alt_subject}")
    
    print(f"合計{filled}個の空きコマを埋めました")

def main():
    """メイン処理"""
    print("最終的な制約違反の修正を開始します")
    
    # パンダス import
    global pd
    import pandas as pd
    
    # CSVを読み込む
    df = script_utils.read_schedule()
    
    # 各種修正を実行
    fix_teacher_conflict(df)
    fix_daily_duplicates(df)
    fix_gym_conflict(df)
    fill_remaining_empty(df)
    
    # CSVを保存
    script_utils.save_schedule(df)
    print("\n修正完了: data/output/output.csv を更新しました")

if __name__ == "__main__":
    main()