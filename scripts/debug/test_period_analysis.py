#!/usr/bin/env python3
"""
テスト期間を除外した違反分析スクリプト
"""

import sys
sys.path.append('/Users/hayashimitsuhiro/Desktop/timetable_v5')

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.config_loader import ConfigLoader
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from collections import defaultdict

def is_test_period(day: str, period: int) -> bool:
    """指定された時間がテスト期間かどうかを判定"""
    test_periods = {
        '月': [1, 2, 3],
        '火': [1, 2, 3],
        '水': [1, 2]
    }
    return day in test_periods and period in test_periods[day]

def analyze_violations_excluding_test():
    print("=== テスト期間を除外した違反分析 ===\n")
    
    # データ読み込み
    repo = CSVScheduleRepository()
    config = ConfigLoader()
    school = config.load_school_structure()
    
    # 時間割読み込み
    schedule_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv"
    schedule = repo.load_schedule(schedule_path, school)
    
    # Follow-upから教師不在情報を読み込み
    followup_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/input/Follow-up.csv"
    import csv
    teacher_absences = defaultdict(list)
    
    with open(followup_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('変更理由') == '教師不在':
                teacher = row.get('変更前教師', '').strip()
                if teacher:
                    day = row.get('曜日', '')
                    period = int(row.get('校時', 0))
                    if day and period:
                        teacher_absences[teacher].append((day, period))
    
    print(f"教師不在情報: {dict(teacher_absences)}\n")
    
    # 違反カテゴリ別カウンタ
    violations = {
        'teacher_absence': [],
        'exchange_sync': [],
        'daily_duplicate': [],
        'gym_usage': [],
        'other': []
    }
    
    # 1. 教師不在違反（テスト期間外）
    print("【1. テスト期間外の教師不在違反】")
    for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
        for period in range(1, 7):
            if is_test_period(day, period):
                continue
                
            for class_name in school.get_all_class_names():
                cell = schedule.get_cell(class_name, day_idx, period - 1)
                if not cell or not cell.subject:
                    continue
                    
                teacher = cell.teacher
                if teacher and teacher in teacher_absences:
                    if (day, period) in teacher_absences[teacher]:
                        violation = f"  - {class_name} {day}{period}校時: {cell.subject} ({teacher}先生不在)"
                        violations['teacher_absence'].append(violation)
                        print(violation)
    
    if not violations['teacher_absence']:
        print("  違反なし")
    print()
    
    # 2. 交流学級同期違反（テスト期間外）
    print("【2. テスト期間外の交流学級同期違反】")
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
        for period in range(1, 7):
            if is_test_period(day, period):
                continue
                
            for exchange_class, parent_class in exchange_pairs.items():
                exchange_cell = schedule.get_cell(exchange_class, day_idx, period - 1)
                parent_cell = schedule.get_cell(parent_class, day_idx, period - 1)
                
                if not exchange_cell or not parent_cell:
                    continue
                
                # 自立活動の場合の特別ルール
                if exchange_cell.subject == '自立':
                    if parent_cell.subject not in ['数', '英']:
                        violation = f"  - {exchange_class} {day}{period}校時が自立のとき、{parent_class}は数/英であるべきですが{parent_cell.subject}です"
                        violations['exchange_sync'].append(violation)
                        print(violation)
                # 通常の同期ルール
                elif exchange_cell.subject in ['国', '社', '数', '理', '英']:
                    if exchange_cell.subject != parent_cell.subject:
                        violation = f"  - {exchange_class}({exchange_cell.subject})と{parent_class}({parent_cell.subject})が{day}{period}校時で不一致"
                        violations['exchange_sync'].append(violation)
                        print(violation)
    
    if not violations['exchange_sync']:
        print("  違反なし")
    print()
    
    # 3. 日内重複違反（テスト期間外）
    print("【3. テスト期間外の日内重複違反】")
    for class_name in school.get_all_class_names():
        for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
            day_subjects = defaultdict(list)
            
            for period in range(1, 7):
                if is_test_period(day, period):
                    continue
                    
                cell = schedule.get_cell(class_name, day_idx, period - 1)
                if cell and cell.subject:
                    # 特別活動系は除外
                    if cell.subject not in ['欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事']:
                        day_subjects[cell.subject].append(period)
            
            for subject, periods in day_subjects.items():
                if len(periods) > 1:
                    violation = f"  - {class_name} {day}曜日: {subject}が{len(periods)}回配置（{', '.join([f'{p}校時' for p in periods])}）"
                    violations['daily_duplicate'].append(violation)
                    print(violation)
    
    if not violations['daily_duplicate']:
        print("  違反なし")
    print()
    
    # 4. 体育館使用違反（テスト期間外）
    print("【4. テスト期間外の体育館使用違反】")
    for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
        for period in range(1, 7):
            if is_test_period(day, period):
                continue
                
            pe_classes = []
            for class_name in school.get_all_class_names():
                cell = schedule.get_cell(class_name, day_idx, period - 1)
                if cell and cell.subject == '保':
                    pe_classes.append(class_name)
            
            if len(pe_classes) > 1:
                violation = f"  - {day}{period}校時: {len(pe_classes)}クラスが同時に体育（{', '.join(pe_classes)}）"
                violations['gym_usage'].append(violation)
                print(violation)
    
    if not violations['gym_usage']:
        print("  違反なし")
    print()
    
    # サマリー
    print("\n=== サマリー ===")
    total_violations = sum(len(v) for v in violations.values())
    print(f"テスト期間外の違反総数: {total_violations}件")
    print(f"  - 教師不在違反: {len(violations['teacher_absence'])}件")
    print(f"  - 交流学級同期違反: {len(violations['exchange_sync'])}件")
    print(f"  - 日内重複違反: {len(violations['daily_duplicate'])}件")
    print(f"  - 体育館使用違反: {len(violations['gym_usage'])}件")
    
    # 空きコマのチェック
    print("\n【空きコマ】")
    empty_slots = []
    for class_name in school.get_all_class_names():
        for day_idx, day in enumerate(['月', '火', '水', '木', '金']):
            for period in range(1, 7):
                cell = schedule.get_cell(class_name, day_idx, period - 1)
                if not cell or not cell.subject:
                    empty_slots.append(f"{class_name} {day}{period}校時")
    
    if empty_slots:
        for slot in empty_slots:
            print(f"  - {slot}")
    else:
        print("  空きコマなし")

if __name__ == "__main__":
    analyze_violations_excluding_test()