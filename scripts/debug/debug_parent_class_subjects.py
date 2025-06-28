#!/usr/bin/env python3
"""親学級の数学・英語配置状況をデバッグ"""

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
    
    print("=== 親学級の数学・英語配置状況 ===\n")
    
    # 親学級と交流学級の対応
    parent_exchange_map = {
        (2, 3): (2, 6),  # 2年3組 → 2年6組
        (3, 3): (3, 6),  # 3年3組 → 3年6組
        (3, 2): (3, 7),  # 3年2組 → 3年7組
    }
    
    for (parent_grade, parent_class), (exchange_grade, exchange_class) in parent_exchange_map.items():
        print(f"\n{parent_grade}年{parent_class}組（親学級） → {exchange_grade}年{exchange_class}組（交流学級）")
        
        # 親学級を取得
        parent_ref = None
        for c in school.get_all_classes():
            if c.grade == parent_grade and c.class_number == parent_class:
                parent_ref = c
                break
        
        # 交流学級を取得
        exchange_ref = None
        for c in school.get_all_classes():
            if c.grade == exchange_grade and c.class_number == exchange_class:
                exchange_ref = c
                break
        
        if parent_ref and exchange_ref:
            # 親学級の数学・英語の時間を確認
            math_eng_slots = []
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    parent_assignment = output_schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        math_eng_slots.append((time_slot, parent_assignment.subject.name))
            
            print(f"  親学級の数学・英語: {len(math_eng_slots)}コマ")
            for slot, subject in math_eng_slots:
                # 交流学級の同じ時間を確認
                exchange_assignment = output_schedule.get_assignment(slot, exchange_ref)
                if exchange_assignment:
                    print(f"    {slot}: 親={subject}, 交流={exchange_assignment.subject.name}")
                else:
                    print(f"    {slot}: 親={subject}, 交流=空き ⭐️")
            
            # 交流学級が自立活動を配置できる空きスロットを探す
            print(f"  交流学級が自立活動を配置可能なスロット:")
            possible_slots = 0
            for slot, subject in math_eng_slots:
                exchange_assignment = output_schedule.get_assignment(slot, exchange_ref)
                if not exchange_assignment:
                    # 固定科目でないか確認
                    if slot.day == "月" and slot.period == 6:
                        continue  # 月曜6限は欠
                    if slot.day in ["火", "水", "金"] and slot.period == 6:
                        continue  # YT
                    if slot.day == "木" and slot.period == 4:
                        continue  # 道徳
                    
                    print(f"    - {slot} （親学級: {subject}）")
                    possible_slots += 1
            
            print(f"  配置可能数: {possible_slots}")
            
            # 交流学級の現在の自立活動を確認
            current_jiritsu = []
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    exchange_assignment = output_schedule.get_assignment(time_slot, exchange_ref)
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        current_jiritsu.append(time_slot)
            
            print(f"  交流学級の現在の自立活動: {len(current_jiritsu)}コマ")
            for slot in current_jiritsu:
                parent_assignment = output_schedule.get_assignment(slot, parent_ref)
                if parent_assignment:
                    print(f"    {slot}: 親={parent_assignment.subject.name}")

if __name__ == "__main__":
    main()