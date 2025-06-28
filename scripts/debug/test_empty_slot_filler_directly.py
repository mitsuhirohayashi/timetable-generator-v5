#!/usr/bin/env python3
"""空きスロット埋めを直接テスト"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_manager import PathManager
from src.domain.value_objects.time_slot import TimeSlot

# 詳細ロギング設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# SmartEmptySlotFillerRefactoredのロガーをDEBUGに設定
logging.getLogger('src.domain.services.smart_empty_slot_filler_refactored').setLevel(logging.DEBUG)

def main():
    # 初期化
    path_manager = PathManager()
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # 学校データ読み込み
    logger.info("=== 学校データ読み込み ===")
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 出力スケジュール読み込み
    logger.info("=== 出力スケジュール読み込み ===")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 空きスロット確認（埋める前）
    empty_before = 0
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                time_slot = TimeSlot(day, period)
                if not output_schedule.get_assignment(time_slot, class_ref):
                    empty_before += 1
    
    logger.info(f"\n埋める前の空きスロット数: {empty_before}")
    
    # 制約システム初期化
    logger.info("\n=== 制約システム初期化 ===")
    from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
    constraint_system = UnifiedConstraintSystem()
    # 制約を登録
    from src.application.services.constraint_registration_service import ConstraintRegistrationService
    registration_service = ConstraintRegistrationService()
    registration_service.register_all_constraints(constraint_system, Path("data"))
    
    # 教師不在情報の読み込み
    logger.info("\n=== 教師不在情報読み込み ===")
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # SmartEmptySlotFillerRefactoredを作成
    logger.info("\n=== SmartEmptySlotFillerRefactored実行 ===")
    filler = SmartEmptySlotFillerRefactored(constraint_system, absence_loader)
    
    # テストのため、スケジュールをコピー
    from src.domain.entities.schedule import Schedule
    test_schedule = Schedule()
    
    # すべての割り当てをコピー
    for time_slot, assignment in output_schedule.get_all_assignments():
        test_schedule.assign(time_slot, assignment)
    
    # ロック状態をコピー
    for time_slot, assignment in output_schedule.get_all_assignments():
        if output_schedule.is_locked(time_slot, assignment.class_ref):
            test_schedule.lock_cell(time_slot, assignment.class_ref)
    
    # 空きスロットを埋める（1パスのみ）
    filled_count = filler.fill_empty_slots_smartly(test_schedule, school, max_passes=1)
    
    logger.info(f"\n埋めたスロット数: {filled_count}")
    
    # 空きスロット確認（埋めた後）
    empty_after = 0
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                time_slot = TimeSlot(day, period)
                if not test_schedule.get_assignment(time_slot, class_ref):
                    empty_after += 1
    
    logger.info(f"埋めた後の空きスロット数: {empty_after}")
    logger.info(f"削減された空きスロット: {empty_before - empty_after}")
    
    # 3年生6限の変化を確認
    logger.info("\n=== 3年生6限の変化 ===")
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3:
            for day in ["月", "火", "水"]:
                time_slot = TimeSlot(day, 6)
                before = output_schedule.get_assignment(time_slot, class_ref)
                after = test_schedule.get_assignment(time_slot, class_ref)
                
                if before != after:
                    before_str = f"{before.subject.name}" if before else "空き"
                    after_str = f"{after.subject.name}" if after else "空き"
                    logger.info(f"{class_ref} {day}6限: {before_str} → {after_str}")

if __name__ == "__main__":
    main()