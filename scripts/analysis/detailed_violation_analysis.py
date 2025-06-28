#!/usr/bin/env python3
"""詳細な違反分析 - 空きスロット、日内重複、教師不在を徹底チェック"""

import csv
from typing import List, Dict, Tuple, Set
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.domain.value_objects.time_slot import TimeSlot

def read_csv(filepath: str) -> List[List[str]]:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def get_time_slot_name(col_idx: int) -> str:
    """列番号から時間枠名を取得"""
    days = ['月', '火', '水', '木', '金']
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    if day_idx < len(days):
        return f'{days[day_idx]}曜{period}限'
    return f'列{col_idx}'

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
                
                # 終日不在の場合
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

def load_teacher_mapping() -> Dict[Tuple[str, str], str]:
    """教師配置マッピングを読み込む"""
    mapping = {}
    try:
        with open('data/config/teacher_subject_mapping.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                class_name = row['Class'].strip()
                subject = row['Subject'].strip()
                teacher = row['Teacher'].strip()
                if teacher and teacher != '-':
                    mapping[(class_name, subject)] = teacher
    except FileNotFoundError:
        print("⚠️  teacher_subject_mapping.csv が見つかりません")
    except Exception as e:
        print(f"⚠️  教師マッピング読み込みエラー: {e}")
    
    return mapping

def main():
    # ファイルを読み込み
    output_data = read_csv('data/output/output.csv')
    teacher_absences = get_teacher_absences()
    teacher_mapping = load_teacher_mapping()
    
    print('=== 詳細な違反分析 ===\n')
    
    # 1. 空きスロットの分析
    print('【1. 空きスロット分析】')
    empty_slots = []
    
    for row_idx in range(2, len(output_data)):
        if row_idx >= len(output_data):
            continue
            
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
            
        class_name = row[0].strip()
        
        for col_idx in range(1, min(31, len(row))):
            value = row[col_idx].strip() if col_idx < len(row) else ''
            
            if not value:  # 空きスロット
                time_slot = get_time_slot_name(col_idx)
                empty_slots.append((class_name, time_slot, col_idx))
    
    if empty_slots:
        print(f'⚠️  空きスロット: {len(empty_slots)}件')
        for class_name, time_slot, col_idx in empty_slots:
            print(f'  - {class_name} {time_slot}')
            # 配置可能な科目を提案
            print(f'    → 配置可能: 国、数、英、理、社、音、美、保、技、家')
    else:
        print('✅ 空きスロットなし')
    
    print()
    
    # 2. 日内重複の分析
    print('【2. 日内重複分析】')
    daily_duplicates = []
    
    for row_idx in range(2, len(output_data)):
        if row_idx >= len(output_data):
            continue
            
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
            
        class_name = row[0].strip()
        
        # 各曜日ごとにチェック
        for day_idx in range(5):  # 月〜金
            day_subjects = {}
            day_name = ['月', '火', '水', '木', '金'][day_idx]
            
            for period in range(1, 7):  # 1〜6限
                col_idx = day_idx * 6 + period
                if col_idx < len(row):
                    subject = row[col_idx].strip()
                    if subject and subject not in ['YT', '道', '欠']:  # 固定科目は除外
                        if subject in day_subjects:
                            daily_duplicates.append({
                                'class': class_name,
                                'day': day_name,
                                'subject': subject,
                                'periods': [day_subjects[subject], period]
                            })
                        else:
                            day_subjects[subject] = period
    
    if daily_duplicates:
        print(f'❌ 日内重複: {len(daily_duplicates)}件')
        for dup in daily_duplicates:
            print(f'  - {dup["class"]} {dup["day"]}曜日: 「{dup["subject"]}」が{dup["periods"][0]}限と{dup["periods"][1]}限に重複')
    else:
        print('✅ 日内重複なし')
    
    print()
    
    # 3. 教師不在チェック
    print('【3. 教師不在チェック】')
    print(f'Follow-up.csvから読み込んだ教師不在情報: {len(teacher_absences)}名')
    for teacher, absences in teacher_absences.items():
        print(f'  - {teacher}先生: {len(absences)}コマ不在')
        for day, period in absences[:3]:  # 最初の3つを表示
            print(f'    → {day}曜{period}限')
        if len(absences) > 3:
            print(f'    ... 他 {len(absences) - 3} コマ')
    
    print()
    
    # 不在時間に授業が割り当てられているかチェック
    absence_violations = []
    
    for row_idx in range(2, len(output_data)):
        if row_idx >= len(output_data):
            continue
            
        row = output_data[row_idx]
        if not row or not row[0]:
            continue
            
        class_name = row[0].strip()
        
        for col_idx in range(1, min(31, len(row))):
            subject = row[col_idx].strip() if col_idx < len(row) else ''
            if not subject:
                continue
            
            # この授業の教師を特定
            teacher = teacher_mapping.get((class_name, subject), None)
            if not teacher:
                continue
            
            # 時間枠を特定
            days = ['月', '火', '水', '木', '金']
            day_idx = (col_idx - 1) // 6
            period = ((col_idx - 1) % 6) + 1
            if day_idx < len(days):
                day = days[day_idx]
                
                # 教師不在チェック
                if teacher in teacher_absences:
                    if (day, period) in teacher_absences[teacher]:
                        time_slot = get_time_slot_name(col_idx)
                        absence_violations.append({
                            'class': class_name,
                            'time': time_slot,
                            'subject': subject,
                            'teacher': teacher
                        })
    
    if absence_violations:
        print(f'❌ 教師不在違反: {len(absence_violations)}件')
        for v in absence_violations:
            print(f'  - {v["class"]} {v["time"]}: {v["subject"]}（{v["teacher"]}先生が不在）')
    else:
        print('✅ 教師不在違反なし')
    
    print()
    
    # 4. 総括
    print('【総括】')
    total_issues = len(empty_slots) + len(daily_duplicates) + len(absence_violations)
    print(f'合計問題数: {total_issues}件')
    print(f'  - 空きスロット: {len(empty_slots)}件')
    print(f'  - 日内重複: {len(daily_duplicates)}件')
    print(f'  - 教師不在違反: {len(absence_violations)}件')
    
    if total_issues > 0:
        print('\n⚠️  これらの問題を修正する必要があります')

if __name__ == "__main__":
    main()