#!/usr/bin/env python3
"""包括的な違反分析"""

import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.utils import parse_class_reference

def analyze_all_violations(schedule_file):
    """すべての違反を詳細分析"""
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # データ読み込み
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    schedule = schedule_repo.load(schedule_file, school)
    
    print(f"\n=== {schedule_file} の違反分析 ===")
    
    violations = {
        'teacher_conflicts': [],
        'daily_duplicates': [],
        'standard_hours': defaultdict(list),
        'exchange_sync': [],
        'jiritsu_conditions': [],
        'grade5_sync': []
    }
    
    # 1. 教師重複チェック
    teacher_assignments = defaultdict(lambda: defaultdict(list))
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[time_slot][assignment.teacher.name].append(str(class_ref))
    
    for time_slot, teachers in teacher_assignments.items():
        for teacher, classes in teachers.items():
            if len(classes) > 1:
                # 5組の合同授業を除外
                if not all('5組' in c for c in classes):
                    violations['teacher_conflicts'].append({
                        'time': str(time_slot),
                        'teacher': teacher,
                        'classes': classes
                    })
    
    # 2. 日内重複チェック
    for class_ref in school.get_all_classes():
        daily_subjects = defaultdict(list)
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    daily_subjects[day].append((period, assignment.subject.name))
        
        for day, subjects in daily_subjects.items():
            subject_count = defaultdict(int)
            for _, subject in subjects:
                subject_count[subject] += 1
            
            for subject, count in subject_count.items():
                if count > 1 and subject not in ['欠', 'YT', '学活', '総合', '道徳']:
                    violations['daily_duplicates'].append({
                        'class': str(class_ref),
                        'day': day,
                        'subject': subject,
                        'count': count
                    })
    
    # 3. 5組同期チェック
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    for day in ['月', '火', '水', '木', '金']:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            subjects = {}
            for class_name in grade5_classes:
                class_ref = parse_class_reference(class_name)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subjects[class_name] = assignment.subject.name
                else:
                    subjects[class_name] = "空き"
            
            unique_subjects = set(subjects.values())
            if len(unique_subjects) > 1:
                violations['grade5_sync'].append({
                    'time': f"{day}曜{period}限",
                    'subjects': subjects
                })
    
    # 4. 交流学級同期チェック
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    for exchange, parent in exchange_pairs.items():
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                exchange_ref = parse_class_reference(exchange)
                parent_ref = parse_class_reference(parent)
                
                exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                
                if exchange_assignment and parent_assignment:
                    exchange_subject = exchange_assignment.subject.name if exchange_assignment.subject else "空き"
                    parent_subject = parent_assignment.subject.name if parent_assignment.subject else "空き"
                    
                    # 自立活動以外で異なる場合は違反
                    if exchange_subject != parent_subject and exchange_subject != '自立':
                        violations['exchange_sync'].append({
                            'time': str(time_slot),
                            'exchange': exchange,
                            'parent': parent,
                            'exchange_subject': exchange_subject,
                            'parent_subject': parent_subject
                        })
                    
                    # 自立活動の条件チェック
                    if exchange_subject == '自立' and parent_subject not in ['数', '英']:
                        violations['jiritsu_conditions'].append({
                            'time': str(time_slot),
                            'exchange': exchange,
                            'parent': parent,
                            'parent_subject': parent_subject
                        })
    
    # 結果サマリー
    print(f"\n違反サマリー:")
    print(f"- 教師重複: {len(violations['teacher_conflicts'])}件")
    print(f"- 日内重複: {len(violations['daily_duplicates'])}件")
    print(f"- 5組同期: {len(violations['grade5_sync'])}件")
    print(f"- 交流学級同期: {len(violations['exchange_sync'])}件")
    print(f"- 自立活動条件: {len(violations['jiritsu_conditions'])}件")
    
    # 詳細表示（各カテゴリ最初の3件）
    if violations['teacher_conflicts']:
        print(f"\n教師重複の例:")
        for v in violations['teacher_conflicts'][:3]:
            print(f"  {v['time']}: {v['teacher']}先生 - {', '.join(v['classes'])}")
    
    if violations['grade5_sync']:
        print(f"\n5組同期違反の例:")
        for v in violations['grade5_sync'][:3]:
            print(f"  {v['time']}: {v['subjects']}")
    
    return violations

def main():
    # 元のファイル
    print("\n" + "="*60)
    original = analyze_all_violations("data/output/output.csv")
    
    # 修正後のファイル（交流学級同期修正済み）
    print("\n" + "="*60)
    from pathlib import Path
    if Path("data/output/output_exchange_sync_fixed.csv").exists():
        fixed = analyze_all_violations("data/output/output_exchange_sync_fixed.csv")
    else:
        fixed = analyze_all_violations("data/output/output_grade5_sync_fixed.csv")
    
    # 改善分析
    print("\n" + "="*60)
    print("=== 改善結果 ===")
    print(f"- 教師重複: {len(original['teacher_conflicts'])} → {len(fixed['teacher_conflicts'])}")
    print(f"- 日内重複: {len(original['daily_duplicates'])} → {len(fixed['daily_duplicates'])}")
    print(f"- 5組同期: {len(original['grade5_sync'])} → {len(fixed['grade5_sync'])}")
    print(f"- 交流学級同期: {len(original['exchange_sync'])} → {len(fixed['exchange_sync'])}")
    print(f"- 自立活動条件: {len(original['jiritsu_conditions'])} → {len(fixed['jiritsu_conditions'])}")

if __name__ == "__main__":
    main()