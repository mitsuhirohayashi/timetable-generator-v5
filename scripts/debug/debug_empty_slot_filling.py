#!/usr/bin/env python3
"""空きスロット埋め処理をデバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import PathManager
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.domain.value_objects.time_slot import TimeSlot

# 詳細ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def debug_empty_slot_filling():
    """空きスロット埋め処理の詳細デバッグ"""
    
    # 初期化
    path_manager = PathManager()
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # 学校データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    logger.info(f"学校データ読み込み完了: {len(school.get_all_classes())}クラス")
    
    # 初期スケジュール読み込み
    initial_schedule = schedule_repo.load_desired_schedule("input/input.csv", school)
    
    # 出力スケジュール読み込み（生成後）
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    
    # 教師不在情報の読み込み
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # SmartEmptySlotFillerRefactoredを作成
    filler = SmartEmptySlotFillerRefactored(constraint_system, absence_loader)
    
    # 空きスロットを手動で検出
    logger.info("\n=== 空きスロットの手動検出 ===")
    empty_slots = []
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = output_schedule.get_assignment(time_slot, class_ref)
                
                if not assignment:
                    # _should_skip_slotメソッドをテスト
                    should_skip = filler._should_skip_slot(time_slot, class_ref)
                    
                    # ロック状態をチェック
                    is_locked = output_schedule.is_locked(time_slot, class_ref)
                    
                    # テスト期間かチェック
                    is_test = filler.constraint_validator.is_test_period(time_slot)
                    
                    empty_slots.append({
                        'time_slot': time_slot,
                        'class_ref': class_ref,
                        'should_skip': should_skip,
                        'is_locked': is_locked,
                        'is_test': is_test
                    })
    
    logger.info(f"空きスロット総数: {len(empty_slots)}")
    
    # 3年生の月火水6限を特に確認
    logger.info("\n=== 3年生の月火水6限の詳細 ===")
    for slot_info in empty_slots:
        if (slot_info['class_ref'].grade == 3 and 
            slot_info['time_slot'].period == 6 and 
            slot_info['time_slot'].day in ["月", "火", "水"]):
            
            logger.info(f"\n{slot_info['class_ref']} {slot_info['time_slot']}:")
            logger.info(f"  - should_skip: {slot_info['should_skip']}")
            logger.info(f"  - is_locked: {slot_info['is_locked']}")
            logger.info(f"  - is_test: {slot_info['is_test']}")
    
    # _find_empty_slotsメソッドを直接呼び出し
    logger.info("\n=== _find_empty_slotsメソッドの結果 ===")
    found_empty_slots = filler._find_empty_slots(output_schedule, school)
    logger.info(f"_find_empty_slotsが見つけた空きスロット数: {len(found_empty_slots)}")
    
    # 3年生6限が含まれているか確認
    grade3_6th_count = 0
    for time_slot, class_ref in found_empty_slots:
        if class_ref.grade == 3 and time_slot.period == 6:
            grade3_6th_count += 1
    
    logger.info(f"3年生6限の空きスロット数: {grade3_6th_count}")
    
    # 実際に埋めてみる
    logger.info("\n=== 空きスロット埋め実行 ===")
    # Scheduleのコピーを作成
    from src.domain.entities.schedule import Schedule
    test_schedule = Schedule()
    
    # output_scheduleの内容をコピー
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            for class_ref in school.get_all_classes():
                assignment = output_schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    test_schedule.assign(time_slot, assignment)
                if output_schedule.is_locked(time_slot, class_ref):
                    test_schedule.lock_cell(time_slot, class_ref)
    
    # 埋める前の統計
    before_empty = 0
    for day in days:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                time_slot = TimeSlot(day, period)
                if not test_schedule.get_assignment(time_slot, class_ref):
                    before_empty += 1
    
    logger.info(f"埋める前の空きスロット数: {before_empty}")
    
    # 実行
    filled_count = filler.fill_empty_slots_smartly(test_schedule, school, max_passes=1)
    logger.info(f"埋めたスロット数: {filled_count}")
    
    # 埋めた後の統計
    after_empty = 0
    for day in days:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                time_slot = TimeSlot(day, period)
                if not test_schedule.get_assignment(time_slot, class_ref):
                    after_empty += 1
    
    logger.info(f"埋めた後の空きスロット数: {after_empty}")
    
    # 不足科目の確認
    logger.info("\n=== 3年1組の不足科目確認 ===")
    class_3_1 = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 1:
            class_3_1 = class_ref
            break
    
    if class_3_1:
        shortage = filler._get_shortage_subjects_prioritized(test_schedule, school, class_3_1)
        logger.info(f"3年1組の科目優先度:")
        for subject, score in list(shortage.items())[:10]:
            logger.info(f"  - {subject.name}: スコア {score}")

def main():
    """メイン処理"""
    logger.info("空きスロット埋め処理のデバッグを開始")
    debug_empty_slot_filling()

if __name__ == "__main__":
    main()