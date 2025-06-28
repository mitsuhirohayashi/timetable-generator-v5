#!/usr/bin/env python3
"""教師重複制約の詳細デバッグV2"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 特定のケースをチェック: 3年1組 火曜6限
    time_slot = TimeSlot("火", 6)
    test_class = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 1:
            test_class = class_ref
            break
    
    print(f"=== {test_class} {time_slot} の状況分析 ===\n")
    
    # 火曜6限の全クラスの状況を確認
    print("火曜6限の全クラスの授業:")
    assignments_by_teacher = {}
    
    for class_ref in school.get_all_classes():
        assignment = output_schedule.get_assignment(time_slot, class_ref)
        if assignment:
            teacher_name = assignment.teacher.name if assignment.teacher else "教師未設定"
            subject_name = assignment.subject.name
            
            if teacher_name not in assignments_by_teacher:
                assignments_by_teacher[teacher_name] = []
            assignments_by_teacher[teacher_name].append(f"{class_ref}: {subject_name}")
    
    for teacher_name, classes in sorted(assignments_by_teacher.items()):
        print(f"\n{teacher_name}先生:")
        for class_info in classes:
            print(f"  - {class_info}")
    
    # 空きクラスを表示
    print("\n空きクラス:")
    empty_count = 0
    for class_ref in school.get_all_classes():
        assignment = output_schedule.get_assignment(time_slot, class_ref)
        if not assignment:
            print(f"  - {class_ref}")
            empty_count += 1
    print(f"合計: {empty_count}クラスが空き")
    
    # 数学を教えられる教師で、火曜6限が空いている教師を探す
    print(f"\n=== 数学を教えられる教師の火曜6限の状況 ===")
    
    math_subject = Subject("数")
    math_teachers = school.get_subject_teachers(math_subject)
    
    available_teachers = []
    for teacher in math_teachers:
        # その教師が火曜6限に教えているクラスを確認
        teaching_classes = []
        for class_ref in school.get_all_classes():
            assignment = output_schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                teaching_classes.append(class_ref)
        
        if teaching_classes:
            print(f"\n{teacher.name}先生: {len(teaching_classes)}クラスで授業中")
            for cls in teaching_classes:
                print(f"  - {cls}")
        else:
            print(f"\n{teacher.name}先生: 空いています")
            available_teachers.append(teacher)
    
    print(f"\n数学を教えられる教師: {len(math_teachers)}人")
    print(f"火曜6限が空いている教師: {len(available_teachers)}人")
    
    # 5組の合同授業をチェック
    print("\n=== 5組の状況確認 ===")
    grade5_classes = []
    for class_ref in school.get_all_classes():
        if class_ref.class_number == 5:
            grade5_classes.append(class_ref)
            assignment = output_schedule.get_assignment(time_slot, class_ref)
            if assignment:
                print(f"{class_ref}: {assignment.subject.name} ({assignment.teacher.name if assignment.teacher else '教師未設定'})")
            else:
                print(f"{class_ref}: 空き")

if __name__ == "__main__":
    main()