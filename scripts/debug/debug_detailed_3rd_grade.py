#!/usr/bin/env python3
"""3年生6限の詳細デバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_manager import PathManager
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.domain.entities.schedule import Schedule

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    # 初期化
    path_manager = PathManager()
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    registration_service = ConstraintRegistrationService()
    registration_service.register_all_constraints(constraint_system, Path("data"))
    
    # 教師不在情報
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # SmartEmptySlotFillerRefactoredを作成
    filler = SmartEmptySlotFillerRefactored(constraint_system, absence_loader)
    
    print("=== 3年生6限の配置可能性詳細チェック ===\n")
    
    # 3年生の全クラスをチェック
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number in [1, 2, 3, 7]:  # 通常クラスのみ
            for day in ["月", "火", "水"]:
                time_slot = TimeSlot(day, 6)
                
                # 現在の割り当てをチェック
                current = output_schedule.get_assignment(time_slot, class_ref)
                if not current:  # 空きスロットのみチェック
                    print(f"\n{class_ref} {day}曜6限:")
                    
                    # 不足科目を取得
                    shortage = filler._get_shortage_subjects_prioritized(output_schedule, school, class_ref)
                    
                    # 利用可能な教師をチェック
                    available_count = 0
                    for subject in list(shortage.keys())[:5]:  # 上位5科目
                        teachers = list(school.get_subject_teachers(subject))
                        available_teachers = []
                        
                        for teacher in teachers:
                            # その時間の教師の状況をチェック
                            busy_classes = []
                            for other_class in school.get_all_classes():
                                if other_class != class_ref:
                                    other_assignment = output_schedule.get_assignment(time_slot, other_class)
                                    if other_assignment and other_assignment.teacher == teacher:
                                        busy_classes.append(str(other_class))
                            
                            if not busy_classes:
                                available_teachers.append(teacher)
                        
                        if available_teachers:
                            available_count += 1
                            print(f"  {subject.name}: {len(available_teachers)}人の教師が利用可能")
                            
                            # 最初の利用可能な教師で配置テスト
                            test_teacher = available_teachers[0]
                            assignment = Assignment(class_ref, subject, test_teacher)
                            can_place, error = filler.constraint_validator.can_place_assignment(
                                output_schedule, school, time_slot, assignment, 'relaxed'
                            )
                            if can_place:
                                print(f"    → {test_teacher.name}先生で配置可能！")
                            else:
                                print(f"    → {test_teacher.name}先生: {error}")
                        else:
                            print(f"  {subject.name}: 全教師が他クラスで授業中")
                    
                    if available_count == 0:
                        print("  → 配置可能な科目・教師の組み合わせがありません")

if __name__ == "__main__":
    main()