#!/usr/bin/env python3
"""
実在の教師のみを使用した現実的な解決策を分析するスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.subject_validator import SubjectValidator
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from collections import defaultdict
import pandas as pd

def load_teacher_mapping():
    """教師と科目のマッピングを読み込む"""
    mapping_path = "data/config/teacher_subject_mapping.csv"
    df = pd.read_csv(mapping_path, encoding='utf-8-sig')
    
    teacher_subjects = defaultdict(set)
    subject_teachers = defaultdict(set)
    
    for _, row in df.iterrows():
        teacher = row['教員名'].strip()
        subject = row['教科'].strip()
        teacher_subjects[teacher].add(subject)
        subject_teachers[subject].add(teacher)
    
    # Convert sets to lists for easier handling
    teacher_subjects = {k: list(v) for k, v in teacher_subjects.items()}
    subject_teachers = {k: list(v) for k, v in subject_teachers.items()}
    
    return teacher_subjects, subject_teachers

def analyze_conflicts(schedule: Schedule):
    """教師の重複を詳細に分析"""
    conflicts = []
    
    # Get all class IDs from assignments
    all_class_ids = set()
    for time_slot, assignment in schedule.get_all_assignments():
        all_class_ids.add(assignment.class_ref)
    
    days = ['月', '火', '水', '木', '金']
    for day_idx in range(5):
        for period in range(6):
            teacher_assignments = defaultdict(list)
            
            for class_ref in all_class_ids:
                time_slot = TimeSlot(days[day_idx], period + 1)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[assignment.teacher.name].append({
                        'class': str(class_ref),
                        'subject': assignment.subject.name
                    })
            
            # 重複をチェック
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [a for a in assignments if '5' in a['class']]
                    other_classes = [a for a in assignments if '5' not in a['class']]
                    
                    # 5組同士の重複は問題なし
                    if len(grade5_classes) == len(assignments) and len(assignments) == 3:
                        continue
                    
                    # それ以外の重複は問題
                    if len(assignments) > 1:
                        conflicts.append({
                            'day': day_idx,
                            'period': period,
                            'teacher': teacher,
                            'assignments': assignments
                        })
    
    return conflicts

def find_free_slots(schedule: Schedule, subject: str, classes_to_move: list):
    """指定された科目とクラスを移動できる空きスロットを探す"""
    free_slots = []
    days = ['月', '火', '水', '木', '金']
    
    for day_idx in range(5):
        for period in range(6):
            can_place_all = True
            
            for class_ref in classes_to_move:
                time_slot = TimeSlot(days[day_idx], period + 1)
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                # 既に何か配置されている場合はスキップ
                if assignment and assignment.subject:
                    can_place_all = False
                    break
                
                # 日内重複チェック
                has_subject_today = False
                for p in range(6):
                    if p != period:
                        ts = TimeSlot(days[day_idx], p + 1)
                        a = schedule.get_assignment(ts, class_ref)
                        if a and a.subject.name == subject:
                            has_subject_today = True
                            break
                
                if has_subject_today:
                    can_place_all = False
                    break
            
            if can_place_all:
                free_slots.append((day_idx, period))
    
    return free_slots

def analyze_realistic_solutions():
    """現実的な解決策を分析"""
    print("=== 実在教師のみを使用した現実的解決策分析 ===\n")
    
    # スケジュールを読み込む
    from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
    reader = CSVScheduleReader()
    schedule = reader.read("data/output/output.csv")
    
    # 教師マッピングを読み込む
    teacher_subjects, subject_teachers = load_teacher_mapping()
    
    print("【教師と担当科目】")
    for subject, teachers in subject_teachers.items():
        print(f"{subject}: {', '.join(teachers)}")
    print()
    
    # 重複を分析
    conflicts = analyze_conflicts(schedule)
    
    print("【現在の教師重複問題】")
    days = ['月', '火', '水', '木', '金']
    for conflict in conflicts:
        day_name = days[conflict['day']]
        period_name = conflict['period'] + 1
        teacher = conflict['teacher']
        classes = [a['class'] for a in conflict['assignments']]
        subjects = list(set([a['subject'] for a in conflict['assignments']]))
        
        print(f"\n{day_name}曜{period_name}限 - {teacher}先生")
        print(f"  担当クラス: {', '.join(classes)} ({len(classes)}クラス)")
        print(f"  科目: {', '.join(subjects)}")
    
    print("\n【解決策の分析】")
    
    # 各重複について解決策を検討
    for conflict in conflicts:
        day_name = days[conflict['day']]
        period_name = conflict['period'] + 1
        teacher = conflict['teacher']
        assignments = conflict['assignments']
        
        print(f"\n◆ {day_name}曜{period_name}限 - {teacher}先生の重複")
        
        # 5組を含む場合の処理
        grade5_assignments = [a for a in assignments if '5' in a['class']]
        other_assignments = [a for a in assignments if '5' not in a['class']]
        
        if grade5_assignments:
            print(f"  5組の合同授業: {', '.join([a['class'] for a in grade5_assignments])}")
            
        if other_assignments:
            print(f"  通常クラス: {', '.join([a['class'] for a in other_assignments])}")
            
            # 移動可能なクラスを探す
            for assignment in other_assignments:
                class_str = assignment['class']
                subject = assignment['subject']
                
                print(f"\n  【{class_str}の{subject}を移動する場合】")
                
                # Find the actual ClassReference object
                class_ref = None
                for ts, a in schedule.get_all_assignments():
                    if str(a.class_ref) == class_str:
                        class_ref = a.class_ref
                        break
                
                if not class_ref:
                    continue
                
                # 空きスロットを探す
                free_slots = find_free_slots(schedule, subject, [class_ref])
                
                if free_slots:
                    print(f"    移動可能なスロット:")
                    for day, period in free_slots[:5]:  # 最初の5つまで表示
                        # その時間に教師が空いているかチェック
                        teacher_free = True
                        # Get all class IDs again
                        all_classes = set()
                        for ts, a in schedule.get_all_assignments():
                            all_classes.add(a.class_ref)
                        
                        for other_class in all_classes:
                            ts = TimeSlot(days[day], period + 1)
                            other_assignment = schedule.get_assignment(ts, other_class)
                            if other_assignment and other_assignment.teacher and other_assignment.teacher.name == teacher:
                                teacher_free = False
                                break
                        
                        if teacher_free:
                            print(f"      - {days[day]}曜{period + 1}限 ✓")
                        else:
                            print(f"      - {days[day]}曜{period + 1}限 (教師が他クラスを担当)")
                else:
                    print(f"    移動可能なスロットがありません")
        
        # 代替教師の検討
        subjects = list(set([a['subject'] for a in assignments]))
        for subject in subjects:
            available_teachers = subject_teachers.get(subject, [])
            print(f"\n  【{subject}の代替教師】")
            if len(available_teachers) == 1:
                print(f"    {available_teachers[0]}先生のみ（代替不可）")
            else:
                print(f"    利用可能: {', '.join(available_teachers)}")
                # 他の教師が空いているかチェック
                for alt_teacher in available_teachers:
                    if alt_teacher != teacher:
                        # この時間に空いているかチェック
                        is_free = True
                        # Get all class IDs
                        all_classes = set()
                        for ts, a in schedule.get_all_assignments():
                            all_classes.add(a.class_ref)
                        
                        for class_ref in all_classes:
                            ts = TimeSlot(days[conflict['day']], conflict['period'] + 1)
                            assignment = schedule.get_assignment(ts, class_ref)
                            if assignment and assignment.teacher and assignment.teacher.name == alt_teacher:
                                is_free = False
                                break
                        
                        if is_free:
                            print(f"      {alt_teacher}先生 - この時間は空いています ✓")
                        else:
                            print(f"      {alt_teacher}先生 - この時間は他クラスを担当")
    
    print("\n【結論】")
    print("1. 音楽（塚本先生）と家庭（金子み先生）は各1名のみが担当")
    print("2. 5組の合同授業を考慮しても、一部の時間帯で物理的に不可能な配置がある")
    print("3. 解決策：")
    print("   - 授業を他の時間帯に移動する")
    print("   - 現在の教員配置では完全な解決が困難な場合がある")
    print("\n※ これは現実的な制約を考慮した分析です。")
    print("※ 架空の教師を追加することなく、実在の教師のみで検討しています。")

if __name__ == "__main__":
    analyze_realistic_solutions()