#!/usr/bin/env python3
"""
最終的な修正済み時間割の全制約違反を包括的にチェック（シンプル版）
"""

import pandas as pd
import numpy as np
from collections import defaultdict
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def load_schedule_df():
    """時間割CSVを直接読み込む"""
    schedule_path = project_root / "data/output/output_3_6_fixed.csv"
    try:
        return pd.read_csv(schedule_path, encoding='utf-8')
    except:
        return pd.read_csv(schedule_path, encoding='shift_jis')

def load_teacher_mapping():
    """教師と科目のマッピングを読み込む"""
    mapping_path = project_root / "data/config/teacher_subject_mapping.csv"
    try:
        df = pd.read_csv(mapping_path, encoding='utf-8')
    except:
        df = pd.read_csv(mapping_path, encoding='shift_jis')
    
    teacher_subjects = defaultdict(set)
    subject_teachers = defaultdict(set)
    
    for _, row in df.iterrows():
        teacher = row['教師名']
        subjects = str(row['担当科目']).split(',')
        for subject in subjects:
            subject = subject.strip()
            if subject and subject != 'nan':
                teacher_subjects[teacher].add(subject)
                subject_teachers[subject].add(teacher)
    
    return teacher_subjects, subject_teachers

def load_standard_hours():
    """標準時数を読み込む"""
    hours_path = project_root / "data/config/base_timetable.csv"
    try:
        df = pd.read_csv(hours_path, encoding='utf-8')
    except:
        df = pd.read_csv(hours_path, encoding='shift_jis')
    
    standard_hours = {}
    for _, row in df.iterrows():
        class_name = row.iloc[0]  # 最初の列がクラス名
        if pd.isna(class_name) or class_name == '':
            continue
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

def parse_schedule_df(df):
    """DataFrameを時間割データ構造に変換"""
    schedule = {}
    days = ['月', '火', '水', '木', '金']
    
    for _, row in df.iterrows():
        class_name = row.iloc[0]  # 最初の列がクラス名
        if pd.isna(class_name) or class_name == '' or class_name == '基本時間割':
            continue
        
        schedule[class_name] = {}
        col_idx = 1
        
        for day in days:
            schedule[class_name][day] = []
            for period in range(1, 7):
                if col_idx < len(row):
                    subject = row.iloc[col_idx]
                    if pd.isna(subject):
                        subject = ''
                    schedule[class_name][day].append(str(subject).strip())
                else:
                    schedule[class_name][day].append('')
                col_idx += 1
    
    return schedule

def check_teacher_conflicts(schedule, subject_teachers):
    """教師の重複をチェック（テスト期間を除く）"""
    violations = []
    days = ['月', '火', '水', '木', '金']
    
    for day_idx, day in enumerate(days):
        for period_idx in range(6):
            period = period_idx + 1
            
            if is_test_period(day, period):
                continue  # テスト期間はスキップ
            
            # この時間の科目と担当クラスを収集
            subject_classes = defaultdict(list)
            
            for class_name, class_schedule in schedule.items():
                subject = class_schedule[day][period_idx]
                if subject and subject not in ['欠', '空', '']:
                    subject_classes[subject].append(class_name)
            
            # 各科目について教師の重複をチェック
            for subject, classes in subject_classes.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.endswith('5')]
                    if len(grade5_classes) == len(classes):
                        continue  # 5組の合同授業は正常
                    
                    # 同じ科目を複数クラスで教えている場合
                    teachers = subject_teachers.get(subject, set())
                    if len(teachers) == 1:  # 1人の教師しかいない場合は重複
                        violations.append({
                            'type': '教師重複',
                            'day': day,
                            'period': period,
                            'subject': subject,
                            'teacher': list(teachers)[0] if teachers else '不明',
                            'classes': classes
                        })
    
    return violations

def check_daily_duplicates(schedule):
    """日内重複をチェック"""
    violations = []
    days = ['月', '火', '水', '木', '金']
    
    for class_name, class_schedule in schedule.items():
        for day in days:
            subjects_in_day = []
            
            for period_idx, subject in enumerate(class_schedule[day]):
                if subject and subject not in ['欠', '空', '']:
                    subjects_in_day.append((period_idx + 1, subject))
            
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
    days = ['月', '火', '水', '木', '金']
    
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in schedule or parent_class not in schedule:
            continue
        
        exchange_schedule = schedule[exchange_class]
        parent_schedule = schedule[parent_class]
        
        for day in days:
            for period_idx in range(6):
                exchange_subject = exchange_schedule[day][period_idx]
                parent_subject = parent_schedule[day][period_idx]
                
                # 自立活動以外は同じでなければならない
                if exchange_subject not in ['自立', '日生', '作業', '']:
                    if exchange_subject != parent_subject:
                        violations.append({
                            'type': '交流学級同期',
                            'exchange_class': exchange_class,
                            'parent_class': parent_class,
                            'day': day,
                            'period': period_idx + 1,
                            'exchange_subject': exchange_subject,
                            'parent_subject': parent_subject
                        })
    
    return violations

def check_monday_6th_period(schedule):
    """月曜6限のルールをチェック"""
    violations = []
    
    for class_name, class_schedule in schedule.items():
        # 1・2年生のクラスのみチェック
        if class_name.startswith('1年') or class_name.startswith('2年'):
            subject = class_schedule['月'][5]  # 月曜6限
            if subject and subject != '欠':
                violations.append({
                    'type': '月曜6限違反',
                    'class': class_name,
                    'subject': subject,
                    'expected': '欠'
                })
    
    return violations

def check_standard_hours(schedule, standard_hours):
    """標準時数との差をチェック"""
    violations = []
    
    # 各クラスの実際の時数を計算
    actual_hours = defaultdict(lambda: defaultdict(int))
    
    for class_name, class_schedule in schedule.items():
        for day_schedule in class_schedule.values():
            for subject in day_schedule:
                if subject and subject not in ['欠', '空', '']:
                    actual_hours[class_name][subject] += 1
    
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
    
    for class_name, class_schedule in schedule.items():
        class_empty = 0
        for day_schedule in class_schedule.values():
            for subject in day_schedule:
                if not subject or subject in ['空', '']:
                    class_empty += 1
                    total_empty += 1
        
        if class_empty > 0:
            empty_slots[class_name] = class_empty
    
    return empty_slots, total_empty

def main():
    print("=== 最終修正済み時間割の包括的制約チェック ===\n")
    
    # データの読み込み
    schedule_df = load_schedule_df()
    schedule = parse_schedule_df(schedule_df)
    teacher_subjects, subject_teachers = load_teacher_mapping()
    standard_hours = load_standard_hours()
    
    # 各種制約をチェック
    teacher_conflicts = check_teacher_conflicts(schedule, subject_teachers)
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
    
    total_violations = len(teacher_conflicts) + len(daily_duplicates) + len(exchange_sync) + len(monday_6th) + len(standard_violations)
    print(f"\n総違反数: {total_violations}件")
    print(f"（元の142件から{142 - total_violations}件削減、{round((142 - total_violations) / 142 * 100, 1)}%改善）")
    
    print(f"\n【空きスロット】")
    print(f"総空きスロット数: {total_empty}個")
    
    # 詳細表示
    if teacher_conflicts:
        print("\n【教師重複の詳細】")
        for v in teacher_conflicts[:5]:  # 最初の5件のみ表示
            print(f"- {v['day']}曜{v['period']}限: {v['subject']} ({v['teacher']}先生)")
            print(f"  担当クラス: {', '.join(v['classes'])}")
    
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
    
    # 成功したクラスの表示
    classes_with_no_violations = []
    for class_name in schedule.keys():
        has_violation = False
        
        # 各種違反をチェック
        for v in teacher_conflicts:
            if class_name in v.get('classes', []):
                has_violation = True
                break
        
        if not has_violation:
            for v in daily_duplicates:
                if v['class'] == class_name:
                    has_violation = True
                    break
        
        if not has_violation:
            for v in exchange_sync:
                if class_name in [v['exchange_class'], v['parent_class']]:
                    has_violation = True
                    break
        
        if not has_violation:
            for v in monday_6th:
                if v['class'] == class_name:
                    has_violation = True
                    break
        
        if not has_violation:
            classes_with_no_violations.append(class_name)
    
    if classes_with_no_violations:
        print(f"\n【違反のないクラス】")
        print(f"{len(classes_with_no_violations)}クラス: {', '.join(sorted(classes_with_no_violations))}")
    
    print("\n=== チェック完了 ===")

if __name__ == "__main__":
    main()