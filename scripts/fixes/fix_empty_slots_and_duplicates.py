#!/usr/bin/env python3
"""空きスロットを埋めて日内重複を修正する総合修正スクリプト"""

import csv
from typing import List, Dict, Tuple, Set
from pathlib import Path
import sys
import copy

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.domain.value_objects.time_slot import TimeSlot

def read_csv(filepath: str) -> List[List[str]]:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def write_csv(filepath: str, data: List[List[str]]):
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def get_time_slot_info(col_idx: int) -> Tuple[str, int]:
    """列番号から曜日と時限を取得"""
    days = ['月', '火', '水', '木', '金']
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    if day_idx < len(days):
        return days[day_idx], period
    return None, None

def get_teacher_absences() -> Dict[str, List[Tuple[str, int]]]:
    """Follow-up.csvから教師不在情報を読み込む"""
    try:
        parser = NaturalFollowUpParser(Path("data/input"))
        result = parser.parse_file("Follow-up.csv")
        
        teacher_absences = {}
        if "teacher_absences" in result:
            for absence in result["teacher_absences"]:
                teacher = absence.teacher_name
                if teacher not in teacher_absences:
                    teacher_absences[teacher] = []
                
                if not absence.periods:
                    for period in range(1, 7):
                        teacher_absences[teacher].append((absence.day, period))
                else:
                    for period in absence.periods:
                        teacher_absences[teacher].append((absence.day, period))
        
        return teacher_absences
    except Exception as e:
        print(f"教師不在情報の読み込みエラー: {e}")
        return {}

def get_standard_hours() -> Dict[Tuple[str, str], int]:
    """標準時数を読み込む"""
    standard_hours = {}
    try:
        with open('data/config/base_timetable.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                class_name = row['Class'].strip()
                for subject, hours in row.items():
                    if subject != 'Class' and hours:
                        try:
                            standard_hours[(class_name, subject)] = int(hours)
                        except ValueError:
                            pass
    except Exception as e:
        print(f"標準時数読み込みエラー: {e}")
    
    return standard_hours

def count_subject_occurrences(output_data: List[List[str]], class_name: str) -> Dict[str, int]:
    """クラスの科目出現回数をカウント"""
    subject_count = {}
    
    for row_idx in range(2, len(output_data)):
        row = output_data[row_idx]
        if row and row[0] and row[0].strip() == class_name:
            for col_idx in range(1, min(31, len(row))):
                subject = row[col_idx].strip() if col_idx < len(row) else ''
                if subject and subject not in ['', 'YT', '道', '欠']:
                    subject_count[subject] = subject_count.get(subject, 0) + 1
            break
    
    return subject_count

def get_available_subjects_for_slot(
    output_data: List[List[str]], 
    class_name: str, 
    col_idx: int,
    standard_hours: Dict[Tuple[str, str], int]
) -> List[str]:
    """指定スロットに配置可能な科目を取得"""
    
    # 基本的な教科リスト
    basic_subjects = ['国', '数', '英', '理', '社', '音', '美', '保', '技', '家']
    
    # 現在の科目カウント
    subject_count = count_subject_occurrences(output_data, class_name)
    
    # 標準時数と比較して不足している科目を優先
    available_subjects = []
    for subject in basic_subjects:
        current_count = subject_count.get(subject, 0)
        standard = standard_hours.get((class_name, subject), 0)
        
        # まだ標準時数に達していない科目を優先
        if current_count < standard:
            available_subjects.append(subject)
    
    # 標準時数に達している科目も追加（ただし優先度は低い）
    for subject in basic_subjects:
        if subject not in available_subjects:
            available_subjects.append(subject)
    
    return available_subjects

def check_daily_duplicate(output_data: List[List[str]], row_idx: int, col_idx: int, subject: str) -> bool:
    """同じ日に同じ科目が既にあるかチェック"""
    day, _ = get_time_slot_info(col_idx)
    if not day:
        return False
    
    row = output_data[row_idx]
    day_idx = (col_idx - 1) // 6
    
    for period in range(1, 7):
        check_col_idx = day_idx * 6 + period
        if check_col_idx != col_idx and check_col_idx < len(row):
            if row[check_col_idx].strip() == subject:
                return True
    
    return False

def fix_empty_slots(output_data: List[List[str]], standard_hours: Dict[Tuple[str, str], int]) -> int:
    """空きスロットを埋める"""
    fixed_count = 0
    
    # 空きスロットを特定
    empty_slots = []
    for row_idx in range(2, len(output_data)):
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
        
        class_name = row[0].strip()
        
        for col_idx in range(1, min(31, len(row))):
            value = row[col_idx].strip() if col_idx < len(row) else ''
            if not value:  # 空きスロット
                empty_slots.append((row_idx, col_idx, class_name))
    
    # 各空きスロットを埋める
    for row_idx, col_idx, class_name in empty_slots:
        available_subjects = get_available_subjects_for_slot(output_data, class_name, col_idx, standard_hours)
        
        # 日内重複にならない科目を選択
        for subject in available_subjects:
            if not check_daily_duplicate(output_data, row_idx, col_idx, subject):
                output_data[row_idx][col_idx] = subject
                fixed_count += 1
                print(f"✅ {class_name} {get_time_slot_info(col_idx)[0]}曜{get_time_slot_info(col_idx)[1]}限 に「{subject}」を配置")
                break
    
    return fixed_count

def fix_daily_duplicates(output_data: List[List[str]], standard_hours: Dict[Tuple[str, str], int]) -> int:
    """日内重複を修正"""
    fixed_count = 0
    
    for row_idx in range(2, len(output_data)):
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
        
        class_name = row[0].strip()
        
        # 各曜日ごとにチェック
        for day_idx in range(5):  # 月〜金
            day_subjects = {}
            day_name = ['月', '火', '水', '木', '金'][day_idx]
            
            # まず重複を検出
            duplicates = []
            for period in range(1, 7):
                col_idx = day_idx * 6 + period
                if col_idx < len(row):
                    subject = row[col_idx].strip()
                    if subject and subject not in ['YT', '道', '欠', '']:
                        if subject in day_subjects:
                            duplicates.append((col_idx, subject, day_subjects[subject]))
                        else:
                            day_subjects[subject] = col_idx
            
            # 重複を修正
            for dup_col_idx, dup_subject, first_col_idx in duplicates:
                # 他の科目と交換を試みる
                available_subjects = get_available_subjects_for_slot(output_data, class_name, dup_col_idx, standard_hours)
                
                for alt_subject in available_subjects:
                    if alt_subject != dup_subject and not check_daily_duplicate(output_data, row_idx, dup_col_idx, alt_subject):
                        # 他の場所でこの科目を探して交換
                        for search_col_idx in range(1, 31):
                            if search_col_idx != dup_col_idx and search_col_idx < len(row):
                                if row[search_col_idx].strip() == alt_subject:
                                    # 交換実行
                                    row[dup_col_idx] = alt_subject
                                    row[search_col_idx] = dup_subject
                                    fixed_count += 1
                                    print(f"✅ {class_name} {day_name}曜日の重複を修正: {dup_subject} ↔ {alt_subject}")
                                    break
                        break
                else:
                    # 交換できない場合は、重複している方を別の科目に変更
                    for alt_subject in available_subjects:
                        if alt_subject != dup_subject and not check_daily_duplicate(output_data, row_idx, dup_col_idx, alt_subject):
                            row[dup_col_idx] = alt_subject
                            fixed_count += 1
                            print(f"✅ {class_name} {day_name}曜{((dup_col_idx-1)%6)+1}限の「{dup_subject}」を「{alt_subject}」に変更")
                            break
    
    return fixed_count

def main():
    # データ読み込み
    output_data = read_csv('data/output/output.csv')
    standard_hours = get_standard_hours()
    
    print('=== 空きスロット埋めと日内重複修正 ===\n')
    
    # バックアップ作成
    import shutil
    shutil.copy('data/output/output.csv', 'data/output/output_before_fix.csv')
    print('✅ バックアップを作成しました: output_before_fix.csv\n')
    
    # 1. 空きスロットを埋める
    print('【1. 空きスロット埋め】')
    empty_fixed = fix_empty_slots(output_data, standard_hours)
    print(f'→ {empty_fixed}件の空きスロットを埋めました\n')
    
    # 2. 日内重複を修正
    print('【2. 日内重複修正】')
    duplicate_fixed = fix_daily_duplicates(output_data, standard_hours)
    print(f'→ {duplicate_fixed}件の日内重複を修正しました\n')
    
    # 修正後のデータを保存
    write_csv('data/output/output.csv', output_data)
    print('✅ 修正後のデータを保存しました: output.csv\n')
    
    # 結果サマリー
    print('【修正サマリー】')
    print(f'  - 空きスロット埋め: {empty_fixed}件')
    print(f'  - 日内重複修正: {duplicate_fixed}件')
    print(f'  - 合計修正数: {empty_fixed + duplicate_fixed}件')
    
    print('\n修正完了！ check_violations.py で確認してください。')

if __name__ == "__main__":
    main()