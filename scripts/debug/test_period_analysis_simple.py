#!/usr/bin/env python3
"""
テスト期間を除外した違反分析スクリプト（シンプル版）
"""

import csv
from collections import defaultdict
from pathlib import Path

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
    
    # 時間割データ読み込み
    timetable_path = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv")
    timetable = {}
    
    with open(timetable_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        lines = list(reader)
    
    # ヘッダー解析
    days = lines[0][1:]  # 月月月月月月火火火...
    periods = [int(p) for p in lines[1][1:]]  # 1,2,3,4,5,6,1,2,3...
    
    # 時間割データ構築
    for row_idx, row in enumerate(lines[2:]):
        if not row[0] or row[0].strip() == '':
            continue
        class_name = row[0].strip()
        
        for col_idx, subject in enumerate(row[1:]):
            if col_idx < len(days) and col_idx < len(periods):
                day = days[col_idx]
                period = periods[col_idx]
                timetable[(class_name, day, period)] = subject.strip() if subject else ''
    
    # Follow-upから教師不在情報を読み込み（自然言語形式）
    followup_path = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5/data/input/Follow-up.csv")
    teacher_absences = defaultdict(list)
    
    with open(followup_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        lines = content.split('\n')
        
        current_day = None
        day_map = {'月曜日': '月', '火曜日': '火', '水曜日': '水', '木曜日': '木', '金曜日': '金'}
        
        for line in lines:
            # 曜日の識別
            for day_name, day_short in day_map.items():
                if line.startswith(day_name):
                    current_day = day_short
                    break
            
            # 教師不在の識別
            if current_day and ('不在' in line or '振休' in line or '年休' in line):
                # 終日不在
                if '終日不在' in line or '1日不在' in line or '終日年休' in line:
                    # 教師名を抽出
                    if '先生' in line:
                        teacher_part = line.split('先生')[0]
                        teacher = teacher_part.split('は')[-1].strip() if 'は' in teacher_part else teacher_part.strip()
                        for period in range(1, 7):
                            teacher_absences[teacher].append((current_day, period))
                # 特定時間の不在
                elif '5・6時間目' in line or '5・6時間目不在' in line:
                    if '先生' in line:
                        # 複数の先生が記載されている場合
                        if 'と' in line:
                            teachers = line.split('と')
                            for t in teachers:
                                if '先生' in t:
                                    teacher = t.split('先生')[0].strip()
                                    teacher_absences[teacher].extend([(current_day, 5), (current_day, 6)])
                        else:
                            teacher_part = line.split('先生')[0]
                            teacher = teacher_part.strip()
                            teacher_absences[teacher].extend([(current_day, 5), (current_day, 6)])
                # 午後不在
                elif '午後不在' in line or '午後から外勤' in line:
                    if '先生' in line:
                        teacher_part = line.split('先生')[0]
                        teacher = teacher_part.strip()
                        for period in range(5, 7):  # 5,6校時
                            teacher_absences[teacher].append((current_day, period))
    
    print(f"教師不在情報: {dict(teacher_absences)}\n")
    
    # 教師担当マッピング読み込み
    teacher_mapping_path = Path("/Users/hayashimitsuhiro/Desktop/timetable_v5/data/config/teacher_subject_mapping.csv")
    subject_teachers = {}
    
    with open(teacher_mapping_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['教員名'].strip()
            subject = row['教科'].strip()
            grade = row['学年'].strip()
            class_num = row['組'].strip()
            class_name = f"{grade}年{class_num}組"
            subject_teachers[(class_name, subject)] = teacher
    
    # 違反カテゴリ別カウンタ
    violations = {
        'teacher_absence': [],
        'exchange_sync': [],
        'daily_duplicate': [],
        'gym_usage': [],
        'meeting_lock': [],
        'other': []
    }
    
    # 会議情報の定義
    meetings = {
        ('火', 3): {'name': '企画', 'members': ['小野塚', '寺田', '森山', '白石', '箱崎', '井野口', '林田', '菊池', '林', '寺沢']},
        ('火', 4): {'name': 'HF', 'members': ['井野口', '林田', '菊池', '林', '寺沢']},
        ('水', 2): {'name': '特会', 'members': ['永山', '金子み', '井上', '藤井', '西村']},
        ('木', 3): {'name': '生指', 'members': ['永山', '金子み', '井上', '藤井', '西村']}
    }
    
    # 1. 教師不在違反（テスト期間外）
    print("【1. テスト期間外の教師不在違反】")
    for (class_name, day, period), subject in timetable.items():
        if is_test_period(day, period):
            continue
        
        if subject and subject not in ['欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事', '自立', '作業', '日生']:
            # この科目の担当教師を取得
            teacher = subject_teachers.get((class_name, subject))
            if teacher and teacher in teacher_absences:
                if (day, period) in teacher_absences[teacher]:
                    violation = f"  - {class_name} {day}{period}校時: {subject} ({teacher}先生不在)"
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
    
    for exchange_class, parent_class in exchange_pairs.items():
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                if is_test_period(day, period):
                    continue
                
                exchange_subject = timetable.get((exchange_class, day, period), '')
                parent_subject = timetable.get((parent_class, day, period), '')
                
                # 自立活動の場合の特別ルール
                if exchange_subject == '自立':
                    if parent_subject not in ['数', '英']:
                        violation = f"  - {exchange_class} {day}{period}校時が自立のとき、{parent_class}は数/英であるべきですが{parent_subject}です"
                        violations['exchange_sync'].append(violation)
                        print(violation)
                # 通常の同期ルール
                elif exchange_subject in ['国', '社', '数', '理', '英']:
                    if exchange_subject != parent_subject:
                        violation = f"  - {exchange_class}({exchange_subject})と{parent_class}({parent_subject})が{day}{period}校時で不一致"
                        violations['exchange_sync'].append(violation)
                        print(violation)
    
    if not violations['exchange_sync']:
        print("  違反なし")
    print()
    
    # 3. 日内重複違反（テスト期間外）
    print("【3. テスト期間外の日内重複違反】")
    class_names = set(key[0] for key in timetable.keys())
    
    for class_name in sorted(class_names):
        for day in ['月', '火', '水', '木', '金']:
            day_subjects = defaultdict(list)
            
            for period in range(1, 7):
                if is_test_period(day, period):
                    continue
                
                subject = timetable.get((class_name, day, period), '')
                if subject and subject not in ['', '欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事']:
                    day_subjects[subject].append(period)
            
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
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            if is_test_period(day, period):
                continue
            
            pe_classes = []
            for class_name in sorted(class_names):
                subject = timetable.get((class_name, day, period), '')
                if subject == '保':
                    pe_classes.append(class_name)
            
            if len(pe_classes) > 1:
                violation = f"  - {day}{period}校時: {len(pe_classes)}クラスが同時に体育（{', '.join(pe_classes)}）"
                violations['gym_usage'].append(violation)
                print(violation)
    
    if not violations['gym_usage']:
        print("  違反なし")
    print()
    
    # 5. 会議ロック違反（テスト期間外）
    print("【5. テスト期間外の会議ロック違反】")
    for (day, period), meeting_info in meetings.items():
        if is_test_period(day, period):
            continue
            
        for class_name in sorted(class_names):
            subject = timetable.get((class_name, day, period), '')
            if subject and subject not in ['', '欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事']:
                teacher = subject_teachers.get((class_name, subject))
                if teacher and teacher in meeting_info['members']:
                    violation = f"  - {day}{period}校時は{meeting_info['name']}のため{teacher}先生は授業配置不可（{class_name} {subject}）"
                    violations['meeting_lock'].append(violation)
                    print(violation)
    
    if not violations['meeting_lock']:
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
    print(f"  - 会議ロック違反: {len(violations['meeting_lock'])}件")
    
    # 空きコマのチェック
    print("\n【空きコマ】")
    empty_slots = []
    for class_name in sorted(class_names):
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                subject = timetable.get((class_name, day, period), '')
                if not subject:
                    empty_slots.append(f"{class_name} {day}{period}校時")
    
    if empty_slots:
        for slot in empty_slots:
            print(f"  - {slot}")
    else:
        print("  空きコマなし")

if __name__ == "__main__":
    analyze_violations_excluding_test()