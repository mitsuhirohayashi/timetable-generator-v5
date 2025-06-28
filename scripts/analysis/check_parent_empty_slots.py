#!/usr/bin/env python3
"""親学級の空きスロットを確認"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    print("=== 親学級の空きスロット確認 ===\n")
    
    # 親学級を確認
    parent_classes = [(2, 3), (3, 3), (3, 2)]
    
    for grade, class_num in parent_classes:
        print(f"\n{grade}年{class_num}組の空きスロット:")
        
        # クラスを取得
        class_ref = None
        for c in school.get_all_classes():
            if c.grade == grade and c.class_number == class_num:
                class_ref = c
                break
        
        if class_ref:
            empty_slots = []
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = output_schedule.get_assignment(time_slot, class_ref)
                    if not assignment:
                        # 固定科目スロットか確認
                        if time_slot.day == "月" and time_slot.period == 6:
                            continue  # 月曜6限は欠
                        if time_slot.day in ["火", "水", "金"] and time_slot.period == 6:
                            continue  # YT
                        if time_slot.day == "木" and time_slot.period == 4:
                            continue  # 道徳
                        
                        empty_slots.append(time_slot)
            
            for slot in empty_slots:
                print(f"  - {slot}")
            
            print(f"  合計: {len(empty_slots)}個の空きスロット")
            
            # 空きスロットがある場合、そこに数学または英語を配置できるか確認
            if empty_slots:
                print(f"\n  これらのスロットに数学または英語を配置した場合:")
                print(f"  → 対応する交流学級が自立活動を配置できるようになる")

if __name__ == "__main__":
    main()