#!/usr/bin/env python3
"""空きスロットを埋めるスクリプト"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
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
    schedule = schedule_repo.load("output/output.csv", school)
    
    print("=== 空きスロット埋め処理 ===\n")
    
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    
    # 教師不在情報の読み込み
    path_manager = PathManager()
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # SmartEmptySlotFillerを作成
    filler = SmartEmptySlotFiller(constraint_system, absence_loader)
    
    # 空きスロットを埋める
    filled_count = filler.fill_empty_slots_smartly(schedule, school, max_passes=4)
    
    print(f"\n合計 {filled_count} 個のスロットを埋めました")
    
    # 保存
    if filled_count > 0:
        schedule_repo.save_schedule(schedule, "output.csv")
        print("結果をdata/output/output.csvに保存しました")
    else:
        print("埋めるスロットがありませんでした")

if __name__ == "__main__":
    main()