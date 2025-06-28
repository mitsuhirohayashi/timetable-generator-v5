#!/usr/bin/env python3
"""制約エラーの詳細をデバッグ"""

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
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
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
    
    # 3年1組の火曜6限を詳細にテスト
    logger.info("=== 3年1組 火曜6限の詳細テスト ===")
    
    test_class = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 1:
            test_class = class_ref
            break
    
    if test_class:
        time_slot = TimeSlot("火", 6)
        
        # このスロットが空きか確認
        current = output_schedule.get_assignment(time_slot, test_class)
        if not current:
            logger.info(f"{test_class} {time_slot}は空きスロットです")
            
            # should_skip_slotをチェック
            should_skip = filler._should_skip_slot(time_slot, test_class)
            logger.info(f"should_skip_slot: {should_skip}")
            
            # 不足科目を取得
            shortage = filler._get_shortage_subjects_prioritized(output_schedule, school, test_class)
            logger.info(f"\n優先度付き科目リスト（上位5つ）:")
            for i, (subject, score) in enumerate(list(shortage.items())[:5]):
                logger.info(f"  {i+1}. {subject.name}: スコア {score}")
            
            # 各科目・教師の組み合わせをテスト
            logger.info(f"\n各科目の配置可能性をテスト:")
            for subject in list(shortage.keys())[:3]:  # 上位3科目をテスト
                teachers = list(school.get_subject_teachers(subject))
                if teachers:
                    teacher = teachers[0]
                    assignment = Assignment(test_class, subject, teacher)
                    
                    logger.info(f"\n{subject.name} ({teacher.name}先生):")
                    
                    # constraint_validatorのcan_place_assignmentを直接呼び出し
                    can_place, error_msg = filler.constraint_validator.can_place_assignment(
                        output_schedule, school, time_slot, assignment, 'relaxed'
                    )
                    
                    logger.info(f"  配置可能: {can_place}")
                    if not can_place:
                        logger.info(f"  エラー: {error_msg}")

if __name__ == "__main__":
    main()