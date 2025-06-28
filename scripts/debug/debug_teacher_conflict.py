#!/usr/bin/env python3
"""教師重複制約の詳細デバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
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
    
    # 特定のケースをチェック: 3年1組 火曜6限に井上先生で数学
    time_slot = TimeSlot("火", 6)
    test_class = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 1:
            test_class = class_ref
            break
    
    print(f"=== {test_class} {time_slot} 井上先生（数学）の配置テスト ===\n")
    
    # 井上先生を探す
    inoue_teacher = None
    # 数学の教師から探す
    math_subject = None
    for subject in school.subjects.values():
        if subject.name == "数":
            math_subject = subject
            break
    
    if math_subject:
        for teacher in school.get_subject_teachers(math_subject):
            if "井上" in teacher.name:
                inoue_teacher = teacher
                break
    
    if inoue_teacher:
        print(f"井上先生: {inoue_teacher.name}")
        
        # 火曜6限の井上先生の状況を確認
        print(f"\n火曜6限の井上先生の授業:")
        teaching_classes = []
        for class_ref in school.get_all_classes():
            assignment = output_schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == inoue_teacher.name:
                teaching_classes.append(f"{class_ref}: {assignment.subject.name}")
        
        if teaching_classes:
            for teaching in teaching_classes:
                print(f"  - {teaching}")
        else:
            print("  - なし（空いています）")
        
        # 3年1組の現在の割り当てを確認
        current_3_1 = output_schedule.get_assignment(time_slot, test_class)
        if current_3_1:
            print(f"\n{test_class}の現在の割り当て: {current_3_1.subject.name} ({current_3_1.teacher.name}先生)")
        else:
            print(f"\n{test_class}の現在の割り当て: 空き")
        
        # 制約チェック
        print("\n=== 制約チェック（直接） ===")
        
        # UnifiedConstraintValidatorを使用
        from src.domain.services.unified_constraint_validator import UnifiedConstraintValidator
        from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
        from src.application.services.constraint_registration_service import ConstraintRegistrationService
        
        constraint_system = UnifiedConstraintSystem()
        registration_service = ConstraintRegistrationService()
        registration_service.register_all_constraints(constraint_system, Path("data"))
        
        validator = UnifiedConstraintValidator(constraint_system)
        
        if math_subject and inoue_teacher:
            assignment = Assignment(test_class, math_subject, inoue_teacher)
            
            # 教師重複を直接チェック
            print("\n教師重複チェック（手動）:")
            conflict_class = validator.check_teacher_conflict(output_schedule, school, time_slot, assignment)
            if conflict_class:
                print(f"  → 重複あり: {conflict_class}")
            else:
                print("  → 重複なし")
            
            # 全体チェック
            can_place, error = validator.can_place_assignment(
                output_schedule, school, time_slot, assignment, 'relaxed'
            )
            print(f"\n総合判定: 配置{'可能' if can_place else '不可'}")
            if error:
                print(f"エラー: {error}")

if __name__ == "__main__":
    main()