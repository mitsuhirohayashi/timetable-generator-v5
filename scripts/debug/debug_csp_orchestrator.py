#!/usr/bin/env python3
"""CSPオーケストレーターの動作をデバッグ"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.csp_orchestrator import CSPOrchestrator
from src.domain.value_objects.time_slot import TimeSlot

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    initial_schedule = schedule_repo.load("input/input.csv", school)
    
    print("=== CSPオーケストレーターのデバッグ ===\n")
    
    # CSPオーケストレーターは使わずに、直接解析する
    
    # 交流学級の自立活動要求時間を確認
    print("=== 交流学級の自立活動要求時間 ===")
    jiritsu_requirements = {
        "1年6組": 1,
        "1年7組": 1,
        "2年6組": 2,
        "2年7組": 1,
        "3年6組": 2,
        "3年7組": 2
    }
    
    for class_name, required_hours in jiritsu_requirements.items():
        print(f"\n{class_name}: {required_hours}時間")
        
        # 現在の自立活動配置を確認
        grade = int(class_name[0])
        class_num = int(class_name[2])
        class_ref = None
        for c in school.get_all_classes():
            if c.grade == grade and c.class_number == class_num:
                class_ref = c
                break
        
        if class_ref:
            current_jiritsu_count = 0
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "自立":
                        current_jiritsu_count += 1
                        print(f"  既存配置: {time_slot}")
            
            print(f"  現在の配置数: {current_jiritsu_count}/{required_hours}")
            
            # 配置可能なスロットを探す
            print("  配置可能スロット:")
            possible_count = 0
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # スキップすべきスロットか確認
                    if time_slot.day == "月" and time_slot.period == 6:
                        continue  # 月曜6限は欠
                    if time_slot.day in ["火", "水", "金"] and time_slot.period == 6:
                        continue  # YT
                    if time_slot.day == "木" and time_slot.period == 4:
                        continue  # 道徳
                    
                    # 既に割り当てがあるか確認
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name in ["道", "道徳", "YT", "欠", "総", "総合", "学", "学活", "学総", "行", "行事", "テスト", "技家"]:
                        continue  # 固定科目
                    
                    if not assignment:
                        # 対応する親学級を確認
                        parent_grade = grade
                        parent_class = {
                            (1, 6): 1,  # 1年6組 → 1年1組
                            (1, 7): 2,  # 1年7組 → 1年2組
                            (2, 6): 3,  # 2年6組 → 2年3組
                            (2, 7): 2,  # 2年7組 → 2年2組
                            (3, 6): 3,  # 3年6組 → 3年3組
                            (3, 7): 2,  # 3年7組 → 3年2組
                        }.get((grade, class_num))
                        
                        if parent_class:
                            parent_ref = None
                            for c in school.get_all_classes():
                                if c.grade == parent_grade and c.class_number == parent_class:
                                    parent_ref = c
                                    break
                            
                            if parent_ref:
                                parent_assignment = initial_schedule.get_assignment(time_slot, parent_ref)
                                if parent_assignment and parent_assignment.subject.name in ["数", "英", "算"]:
                                    print(f"    - {time_slot}: 親学級が{parent_assignment.subject.name}")
                                    possible_count += 1
            
            print(f"  配置可能数: {possible_count}")

if __name__ == "__main__":
    main()