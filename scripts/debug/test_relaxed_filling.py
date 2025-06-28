#!/usr/bin/env python3
"""リラックス戦略での空きスロット埋めテスト"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_manager import PathManager
from src.domain.value_objects.time_slot import TimeSlot
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.domain.entities.schedule import Schedule

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
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
    
    # スケジュールをコピー
    test_schedule = Schedule()
    for time_slot, assignment in output_schedule.get_all_assignments():
        test_schedule.assign(time_slot, assignment)
    for time_slot, assignment in output_schedule.get_all_assignments():
        if output_schedule.is_locked(time_slot, assignment.class_ref):
            test_schedule.lock_cell(time_slot, assignment.class_ref)
    
    # 埋める前の3年生6限の状況
    logger.info("=== 埋める前の3年生6限 ===")
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3:
            for day in ["月", "火", "水"]:
                time_slot = TimeSlot(day, 6)
                assignment = test_schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    logger.info(f"{class_ref} {day}6限: 空き")
    
    # 複数パスで実行（より緩い戦略まで試す）
    logger.info("\n=== 複数パスで空きスロット埋め ===")
    filled_count = filler.fill_empty_slots_smartly(test_schedule, school, max_passes=4)
    
    logger.info(f"\n合計埋めたスロット数: {filled_count}")
    
    # 埋めた後の3年生6限の状況
    logger.info("\n=== 埋めた後の3年生6限 ===")
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
                elif not after:
                    logger.info(f"{class_ref} {day}6限: まだ空き")
    
    # 統計を表示
    if hasattr(filler, 'stats'):
        logger.info("\n=== 埋め統計 ===")
        for key, value in sorted(filler.stats.items()):
            if value > 0:
                logger.info(f"{key}: {value}")

if __name__ == "__main__":
    main()