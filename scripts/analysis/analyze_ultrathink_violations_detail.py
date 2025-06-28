#!/usr/bin/env python3
"""Ultrathink生成結果の詳細違反分析"""

import sys
import pandas as pd
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader


def load_data():
    """データを読み込む"""
    # School data
    school_repo = CSVSchoolRepository()
    school = school_repo.load_school_data(str(project_root / "data" / "config"))
    
    # Schedule
    schedule_reader = CSVScheduleReader()
    schedule = schedule_reader.read(str(project_root / "data" / "output" / "output.csv"))
    
    # Teacher absences from Follow-up.csv
    absence_loader = TeacherAbsenceLoader()
    teacher_absences = absence_loader.load_teacher_absences(str(project_root / "data" / "input" / "Follow-up.csv"))
    
    return school, schedule, teacher_absences


def analyze_teacher_conflicts(schedule: Schedule, school: School) -> List[Dict]:
    """教師重複を分析"""
    conflicts = []
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = defaultdict(list)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[assignment.teacher.name].append((class_ref, assignment.subject.name))
            
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = {("1年5組", "2年5組", "3年5組")}
                    assigned_classes = set(a[0] for a in assignments)
                    
                    if not (assigned_classes.issubset({"1年5組", "2年5組", "3年5組"}) and 
                           len(assigned_classes) == 3):
                        conflicts.append({
                            'time': f"{day}{period}",
                            'teacher': teacher,
                            'classes': [f"{c}({s})" for c, s in assignments]
                        })
    
    return conflicts


def analyze_daily_duplicates(schedule: Schedule, school: School) -> List[Dict]:
    """日内重複を分析"""
    duplicates = []
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for class_ref in school.get_all_classes():
            subjects_in_day = defaultdict(list)
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subjects_in_day[assignment.subject.name].append(period)
            
            for subject, periods in subjects_in_day.items():
                if len(periods) > 1:
                    duplicates.append({
                        'day': day,
                        'class': class_ref,
                        'subject': subject,
                        'periods': periods
                    })
    
    return duplicates


def analyze_grade5_sync(schedule: Schedule) -> List[Dict]:
    """5組同期を分析"""
    issues = []
    days = ["月", "火", "水", "木", "金"]
    grade5_classes = ["1年5組", "2年5組", "3年5組"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            subjects = {}
            
            for class_ref in grade5_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subjects[class_ref] = assignment.subject.name
                else:
                    subjects[class_ref] = "空き"
            
            # 全て同じかチェック
            unique_subjects = set(subjects.values())
            if len(unique_subjects) > 1:
                issues.append({
                    'time': f"{day}{period}",
                    'subjects': subjects
                })
    
    return issues


def analyze_jiritsu_violations(schedule: Schedule, school: School) -> List[Dict]:
    """自立活動違反を分析"""
    violations = []
    days = ["月", "火", "水", "木", "金"]
    
    # 交流学級と親学級のマッピング
    exchange_parent_map = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for exchange_class, parent_class in exchange_parent_map.items():
                exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                
                if exchange_assignment and parent_assignment:
                    # 交流学級が自立活動の場合
                    if exchange_assignment.subject.name == "自立":
                        # 親学級は数学か英語でなければならない
                        if parent_assignment.subject.name not in ["数", "英"]:
                            violations.append({
                                'time': f"{day}{period}",
                                'exchange_class': exchange_class,
                                'parent_class': parent_class,
                                'parent_subject': parent_assignment.subject.name
                            })
    
    return violations


def analyze_gym_conflicts(schedule: Schedule, school: School) -> List[Dict]:
    """体育館使用競合を分析"""
    conflicts = []
    days = ["月", "火", "水", "木", "金"]
    
    # 交流学級と親学級のペア
    exchange_pairs = [
        ("1年1組", "1年6組"),
        ("1年2組", "1年7組"),
        ("2年3組", "2年6組"),
        ("2年2組", "2年7組"),
        ("3年3組", "3年6組"),
        ("3年2組", "3年7組")
    ]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            pe_classes = []
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == "保":
                    pe_classes.append(class_ref)
            
            # 体育館使用クラスが2つ以上ある場合
            if len(pe_classes) > 1:
                # 交流学級ペアを除外してチェック
                non_paired_classes = []
                paired_classes = []
                
                for pe_class in pe_classes:
                    is_paired = False
                    for parent, exchange in exchange_pairs:
                        if pe_class in [parent, exchange] and parent in pe_classes and exchange in pe_classes:
                            if parent not in paired_classes:
                                paired_classes.extend([parent, exchange])
                            is_paired = True
                            break
                    
                    if not is_paired:
                        non_paired_classes.append(pe_class)
                
                # ペア以外に2つ以上ある場合は違反
                if len(non_paired_classes) > 1 or (len(non_paired_classes) == 1 and len(paired_classes) > 0):
                    conflicts.append({
                        'time': f"{day}{period}",
                        'classes': pe_classes
                    })
    
    return conflicts


def analyze_empty_slots(schedule: Schedule, school: School) -> Dict[str, int]:
    """空きスロットを分析"""
    empty_by_class = defaultdict(int)
    days = ["月", "火", "水", "木", "金"]
    
    for class_ref in school.get_all_classes():
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    empty_by_class[class_ref] += 1
    
    return dict(empty_by_class)


def main():
    """メイン処理"""
    print("Ultrathink生成結果の詳細違反分析")
    print("=" * 80)
    
    # データ読み込み
    school, schedule, teacher_absences = load_data()
    
    # 各種違反を分析
    teacher_conflicts = analyze_teacher_conflicts(schedule, school)
    daily_duplicates = analyze_daily_duplicates(schedule, school)
    grade5_issues = analyze_grade5_sync(schedule)
    jiritsu_violations = analyze_jiritsu_violations(schedule, school)
    gym_conflicts = analyze_gym_conflicts(schedule, school)
    empty_slots = analyze_empty_slots(schedule, school)
    
    # 結果表示
    print(f"\n1. 教師重複 ({len(teacher_conflicts)}件):")
    for conflict in teacher_conflicts[:10]:  # 最初の10件
        print(f"  - {conflict['time']} {conflict['teacher']}先生: {', '.join(conflict['classes'])}")
    if len(teacher_conflicts) > 10:
        print(f"  ... 他{len(teacher_conflicts) - 10}件")
    
    print(f"\n2. 日内重複 ({len(daily_duplicates)}件):")
    for dup in daily_duplicates[:10]:
        print(f"  - {dup['class']} {dup['day']}曜日: {dup['subject']} が {dup['periods']} 時間目に重複")
    if len(daily_duplicates) > 10:
        print(f"  ... 他{len(daily_duplicates) - 10}件")
    
    print(f"\n3. 5組同期違反 ({len(grade5_issues)}件):")
    for issue in grade5_issues[:10]:
        subjects_str = ', '.join([f"{c}:{s}" for c, s in issue['subjects'].items()])
        print(f"  - {issue['time']}: {subjects_str}")
    if len(grade5_issues) > 10:
        print(f"  ... 他{len(grade5_issues) - 10}件")
    
    print(f"\n4. 自立活動違反 ({len(jiritsu_violations)}件):")
    for viol in jiritsu_violations:
        print(f"  - {viol['time']} {viol['exchange_class']}が自立、{viol['parent_class']}が{viol['parent_subject']}")
    
    print(f"\n5. 体育館競合 ({len(gym_conflicts)}件):")
    for conflict in gym_conflicts:
        print(f"  - {conflict['time']}: {', '.join(conflict['classes'])}")
    
    print(f"\n6. 空きスロット数:")
    total_empty = sum(empty_slots.values())
    print(f"  合計: {total_empty}個")
    for class_ref, count in sorted(empty_slots.items(), key=lambda x: -x[1])[:5]:
        print(f"  - {class_ref}: {count}個")
    
    # 総計
    total_violations = len(teacher_conflicts) + len(daily_duplicates) + len(grade5_issues) + len(jiritsu_violations) + len(gym_conflicts)
    print(f"\n総制約違反数: {total_violations}件")
    print(f"空きスロット数: {total_empty}個")
    
    # 推奨対策
    print("\n推奨対策:")
    print("1. 5組同期違反が最も多い - RefactoredGrade5Synchronizerの処理順序を確認")
    print("2. 教師重複は特定の教師に集中している可能性 - 教師別の負荷分析が必要")
    print("3. 空きスロットは後処理で埋める必要がある")
    

if __name__ == "__main__":
    main()