#!/usr/bin/env python3
"""シンプルな空きスロット検出デバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # 学校データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 出力スケジュール読み込み
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 3年生の月火水6限をチェック
    print("\n=== 3年生の月火水6限の状況 ===")
    days = ["月", "火", "水"]
    
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3:
            print(f"\n{class_ref}:")
            for day in days:
                time_slot = TimeSlot(day, 6)
                assignment = output_schedule.get_assignment(time_slot, class_ref)
                is_locked = output_schedule.is_locked(time_slot, class_ref)
                
                if assignment:
                    print(f"  {day}6限: {assignment.subject.name} ({assignment.teacher.name}先生) [Locked={is_locked}]")
                else:
                    print(f"  {day}6限: 空き [Locked={is_locked}]")
    
    # 全体の空きスロット数をカウント
    print("\n=== 空きスロット統計 ===")
    total_slots = 0
    empty_slots = 0
    locked_empty = 0
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            for class_ref in school.get_all_classes():
                total_slots += 1
                time_slot = TimeSlot(day, period)
                assignment = output_schedule.get_assignment(time_slot, class_ref)
                is_locked = output_schedule.is_locked(time_slot, class_ref)
                
                if not assignment:
                    empty_slots += 1
                    if is_locked:
                        locked_empty += 1
    
    print(f"総スロット数: {total_slots}")
    print(f"空きスロット数: {empty_slots} ({empty_slots/total_slots*100:.1f}%)")
    print(f"ロックされた空きスロット: {locked_empty}")
    
    # 3年生6限の特別チェック
    print("\n=== 3年生6限の空きスロット詳細 ===")
    for day in ["月", "火", "水"]:
        empty_count = 0
        locked_count = 0
        
        for class_ref in school.get_all_classes():
            if class_ref.grade == 3:
                time_slot = TimeSlot(day, 6)
                if not output_schedule.get_assignment(time_slot, class_ref):
                    empty_count += 1
                    if output_schedule.is_locked(time_slot, class_ref):
                        locked_count += 1
        
        print(f"{day}曜6限: {empty_count}クラスが空き (うち{locked_count}クラスがロック済み)")

if __name__ == "__main__":
    main()