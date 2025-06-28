#!/usr/bin/env python3
"""
最終的な修正済み時間割の全制約違反を包括的にチェック
"""

import pandas as pd
import numpy as np
from collections import defaultdict
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository

def load_schedule():
    """最新の修正済み時間割を読み込む"""
    csv_repo = CSVScheduleRepository()
    return csv_repo.load("output_3_6_fixed.csv")

def load_teacher_mapping():
    """教師と科目のマッピングを読み込む"""
    mapping_path = project_root / "data/config/teacher_subject_mapping.csv"
    df = pd.read_csv(mapping_path, encoding='shift_jis')
    
    teacher_subjects = defaultdict(set)
    for _, row in df.iterrows():
        teacher = row['教師名']
        subjects = str(row['担当科目']).split(',')
        for subject in subjects:
            subject = subject.strip()
            if subject and subject != 'nan':
                teacher_subjects[teacher].add(subject)
    
    return teacher_subjects

def load_standard_hours():
    """標準時数を読み込む"""
    hours_path = project_root / "data/config/base_timetable.csv"
    df = pd.read_csv(hours_path, encoding='shift_jis')
    
    standard_hours = {}
    for _, row in df.iterrows():
        class_name = row['クラス']
        for col in df.columns[1:]:
            if pd.notna(row[col]) and row[col] > 0:
                standard_hours[(class_name, col)] = int(row[col])
    
    return standard_hours

def is_test_period(day, period):
    """テスト期間かどうか判定"""
    test_periods = {
        ('月', 1), ('月', 2), ('月', 3),
        ('火', 1), ('火', 2), ('火', 3),
        ('水', 1), ('水', 2)
    }
    return (day, period) in test_periods

def check_teacher_conflicts(schedule, teacher_mapping):
    """教師の重複をチェック（テスト期間を除く）"""
    violations = []
    
    # 時間ごとに教師の割り当てを収集
    for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
        for period in range(1, 7):
            if is_test_period(day, period):
                continue  # テスト期間はスキップ
            
            teacher_assignments = defaultdict(list)
            
            for class_name, class_schedule in schedule.get_all_classes().items():
                assignment = class_schedule.get_assignment(day_idx, period - 1)
                if assignment and assignment.subject and assignment.subject not in ['欠', '空', '']:
                    # 教師を特定
                    assigned_teacher = None
                    for teacher, subjects in teacher_mapping.items():
                        if assignment.subject in subjects:
                            # 特定のクラスと科目の組み合わせで教師を確認
                            if assignment.teacher:
                                if assignment.teacher == teacher:
                                    assigned_teacher = teacher
                                    break
                            else:
                                assigned_teacher = teacher
                                break
                    
                    if assigned_teacher:
                        teacher_assignments[assigned_teacher].append((class_name, assignment.subject))
            
            # 重複をチェック
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c, _ in assignments if c.endswith('5')]
                    if len(grade5_classes) == len(assignments) and len(set([s for _, s in assignments])) == 1:
                        continue  # 5組の合同授業は正常
                    
                    violations.append({
                        'type': '教師重複',
                        'day': day,
                        'period': period,
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    return violations

def check_daily_duplicates(schedule):
    """日内重複をチェック"""
    violations = []
    
    for class_name, class_schedule in schedule.get_all_classes().items():
        for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
            subjects_in_day = []
            
            for period in range(6):
                assignment = class_schedule.get_assignment(day_idx, period)
                if assignment and assignment.subject and assignment.subject not in ['欠', '空', '']:
                    subjects_in_day.append((period + 1, assignment.subject))
            
            # 同じ科目が複数回出現しているかチェック
            subject_counts = defaultdict(list)
            for period, subject in subjects_in_day:
                subject_counts[subject].append(period)
            
            for subject, periods in subject_counts.items():
                if len(periods) > 1:
                    violations.append({
                        'type': '日内重複',
                        'class': class_name,
                        'day': day,
                        'subject': subject,
                        'periods': periods
                    })
    
    return violations

def check_exchange_class_sync(schedule):
    """交流学級の同期をチェック"""
    violations = []
    
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in schedule.get_all_classes() or parent_class not in schedule.get_all_classes():
            continue
        
        exchange_schedule = schedule.get_all_classes()[exchange_class]
        parent_schedule = schedule.get_all_classes()[parent_class]
        
        for day_idx in range(5):
            for period in range(6):
                exchange_assignment = exchange_schedule.get_assignment(day_idx, period)
                parent_assignment = parent_schedule.get_assignment(day_idx, period)
                
                exchange_subject = exchange_assignment.subject if exchange_assignment else ''
                parent_subject = parent_assignment.subject if parent_assignment else ''
                
                # 自立活動以外は同じでなければならない
                if exchange_subject not in ['自立', '日生', '作業', '']:
                    if exchange_subject != parent_subject:
                        violations.append({
                            'type': '交流学級同期',
                            'exchange_class': exchange_class,
                            'parent_class': parent_class,
                            'day': ['月', '火', '水', '木', '金'][day_idx],
                            'period': period + 1,
                            'exchange_subject': exchange_subject,
                            'parent_subject': parent_subject
                        })
    
    return violations

def check_monday_6th_period(schedule):
    """月曜6限のルールをチェック"""
    violations = []
    
    for class_name, class_schedule in schedule.get_all_classes().items():
        # 1・2年生のクラスのみチェック
        if class_name.startswith('1年') or class_name.startswith('2年'):
            assignment = class_schedule.get_assignment(0, 5)  # 月曜6限
            if assignment and assignment.subject != '欠':
                violations.append({
                    'type': '月曜6限違反',
                    'class': class_name,
                    'subject': assignment.subject,
                    'expected': '欠'
                })
    
    return violations

def check_standard_hours(schedule, standard_hours):
    """標準時数との差をチェック"""
    violations = []
    
    # 各クラスの実際の時数を計算
    actual_hours = defaultdict(lambda: defaultdict(int))
    
    for class_name, class_schedule in schedule.get_all_classes().items():
        for day_idx in range(5):
            for period in range(6):
                assignment = class_schedule.get_assignment(day_idx, period)
                if assignment and assignment.subject and assignment.subject not in ['欠', '空', '']:
                    actual_hours[class_name][assignment.subject] += 1
    
    # 標準時数と比較
    for (class_name, subject), standard in standard_hours.items():
        if class_name in actual_hours:
            actual = actual_hours[class_name].get(subject, 0)
            if actual != standard:
                violations.append({
                    'type': '標準時数違反',
                    'class': class_name,
                    'subject': subject,
                    'standard': standard,
                    'actual': actual,
                    'difference': actual - standard
                })
    
    return violations

def count_empty_slots(schedule):
    """空きスロットをカウント"""
    empty_slots = defaultdict(int)
    total_empty = 0
    
    for class_name, class_schedule in schedule.get_all_classes().items():
        class_empty = 0
        for day_idx in range(5):
            for period in range(6):
                assignment = class_schedule.get_assignment(day_idx, period)
                if not assignment or not assignment.subject or assignment.subject in ['空', '']:
                    class_empty += 1
                    total_empty += 1
        
        if class_empty > 0:
            empty_slots[class_name] = class_empty
    
    return empty_slots, total_empty

def main():
    print("=== 最終修正済み時間割の包括的制約チェック ===\n")
    
    # データの読み込み
    schedule = load_schedule()
    teacher_mapping = load_teacher_mapping()
    standard_hours = load_standard_hours()
    
    # 各種制約をチェック
    teacher_conflicts = check_teacher_conflicts(schedule, teacher_mapping)
    daily_duplicates = check_daily_duplicates(schedule)
    exchange_sync = check_exchange_class_sync(schedule)
    monday_6th = check_monday_6th_period(schedule)
    standard_violations = check_standard_hours(schedule, standard_hours)
    empty_slots, total_empty = count_empty_slots(schedule)
    
    # 結果の表示
    print("【制約違反サマリー】")
    print(f"1. 教師重複（テスト期間除く）: {len(teacher_conflicts)}件")
    print(f"2. 日内重複: {len(daily_duplicates)}件")
    print(f"3. 交流学級同期違反: {len(exchange_sync)}件")
    print(f"4. 月曜6限違反: {len(monday_6th)}件")
    print(f"5. 標準時数違反: {len(standard_violations)}件")
    print(f"\n総違反数: {len(teacher_conflicts) + len(daily_duplicates) + len(exchange_sync) + len(monday_6th) + len(standard_violations)}件")
    print(f"（元の142件から{142 - (len(teacher_conflicts) + len(daily_duplicates) + len(exchange_sync) + len(monday_6th) + len(standard_violations))}件削減）")
    
    print(f"\n【空きスロット】")
    print(f"総空きスロット数: {total_empty}個")
    
    # 詳細表示
    if teacher_conflicts:
        print("\n【教師重複の詳細】")
        for v in teacher_conflicts[:5]:  # 最初の5件のみ表示
            print(f"- {v['day']}曜{v['period']}限: {v['teacher']}先生")
            print(f"  担当クラス: {v['assignments']}")
    
    if daily_duplicates:
        print("\n【日内重複の詳細】")
        for v in daily_duplicates[:5]:  # 最初の5件のみ表示
            print(f"- {v['class']} {v['day']}曜日: {v['subject']} が {v['periods']} 限に重複")
    
    if exchange_sync:
        print("\n【交流学級同期違反の詳細】")
        for v in exchange_sync[:5]:  # 最初の5件のみ表示
            print(f"- {v['exchange_class']}と{v['parent_class']} {v['day']}曜{v['period']}限")
            print(f"  交流学級: {v['exchange_subject']}, 親学級: {v['parent_subject']}")
    
    if empty_slots:
        print("\n【空きスロットの詳細（上位5クラス）】")
        sorted_empty = sorted(empty_slots.items(), key=lambda x: x[1], reverse=True)
        for class_name, count in sorted_empty[:5]:
            print(f"- {class_name}: {count}個")
    
    print("\n=== チェック完了 ===")

if __name__ == "__main__":
    main()