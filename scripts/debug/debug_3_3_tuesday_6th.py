#!/usr/bin/env python3
"""3年3組の火曜6限が埋まらない理由を調査"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem, AssignmentContext
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_manager import PathManager

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    
    # 教師不在情報の読み込み
    path_manager = PathManager()
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # 3年3組を取得
    class_3_3 = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 3:
            class_3_3 = class_ref
            break
    
    time_slot = TimeSlot("火", 6)
    
    print(f"=== {class_3_3} {time_slot} の状況分析 ===\n")
    
    # 現在の割り当て状況を確認
    current = output_schedule.get_assignment(time_slot, class_3_3)
    if current:
        print(f"現在の割り当て: {current.subject.name} ({current.teacher.name if current.teacher else '教師未設定'})")
    else:
        print("現在: 空きスロット")
    
    # ロック状態確認
    if output_schedule.is_locked(time_slot, class_3_3):
        print("※ このスロットはロックされています")
    
    # 各教科を配置できるかチェック
    print("\n=== 各教科の配置可能性チェック ===")
    subjects_to_try = ["数", "英", "国", "理", "社", "音", "美", "保", "技", "家"]
    
    for subject_name in subjects_to_try:
        subject = Subject(subject_name)
        teachers = school.get_subject_teachers(subject)
        
        print(f"\n{subject_name}科:")
        print(f"  教えられる教師: {[t.name for t in teachers]}")
        
        placed = False
        for teacher in teachers:
            # 仮の割り当てを作成
            test_assignment = Assignment(class_3_3, subject, teacher)
            
            # 制約チェック
            context = AssignmentContext(
                schedule=output_schedule,
                school=school,
                time_slot=time_slot,
                assignment=test_assignment
            )
            result, reasons = constraint_system.check_before_assignment(context)
            
            if result:
                print(f"  ✓ {teacher.name}先生で配置可能")
                placed = True
                break
            else:
                print(f"  ✗ {teacher.name}先生: {', '.join(reasons)}")
        
        if not placed:
            print("  → 配置不可")
    
    # 火曜日の3年3組の時間割を確認
    print("\n=== 火曜日の3年3組の時間割 ===")
    for period in range(1, 7):
        ts = TimeSlot("火", period)
        assignment = output_schedule.get_assignment(ts, class_3_3)
        if assignment:
            print(f"{period}限: {assignment.subject.name} ({assignment.teacher.name if assignment.teacher else '教師未設定'})")
        else:
            print(f"{period}限: 空き")
    
    # 日内重複チェック
    print("\n=== 火曜日の日内重複状況 ===")
    subject_counts = {}
    for period in range(1, 7):
        ts = TimeSlot("火", period)
        assignment = output_schedule.get_assignment(ts, class_3_3)
        if assignment:
            subject_name = assignment.subject.name
            if subject_name not in subject_counts:
                subject_counts[subject_name] = 0
            subject_counts[subject_name] += 1
    
    for subject_name, count in sorted(subject_counts.items()):
        print(f"{subject_name}: {count}回")

if __name__ == "__main__":
    main()