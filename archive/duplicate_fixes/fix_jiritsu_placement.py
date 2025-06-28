#!/usr/bin/env python3
"""自立活動配置を修正するスクリプト"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    schedule = schedule_repo.load("output/output.csv", school)
    
    print("=== 自立活動配置の修正 ===\n")
    
    # 交流学級の自立活動要求
    jiritsu_requirements = {
        (2, 6): 2,  # 2年6組: 2時間必要
        (3, 6): 2,  # 3年6組: 2時間必要
        (3, 7): 2,  # 3年7組: 2時間必要
    }
    
    # 親学級との対応
    parent_map = {
        (2, 6): (2, 3),  # 2年6組 ← 2年3組
        (3, 6): (3, 3),  # 3年6組 ← 3年3組
        (3, 7): (3, 2),  # 3年7組 ← 3年2組
    }
    
    fixed_count = 0
    
    for (exchange_grade, exchange_class), required_hours in jiritsu_requirements.items():
        parent_grade, parent_class = parent_map[(exchange_grade, exchange_class)]
        
        # クラス参照を取得
        exchange_ref = None
        parent_ref = None
        for c in school.get_all_classes():
            if c.grade == exchange_grade and c.class_number == exchange_class:
                exchange_ref = c
            elif c.grade == parent_grade and c.class_number == parent_class:
                parent_ref = c
        
        if not exchange_ref or not parent_ref:
            continue
        
        print(f"\n{exchange_ref} (必要: {required_hours}時間)")
        
        # 現在の自立活動数を確認
        current_jiritsu = 0
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(slot, exchange_ref)
                if assignment and assignment.subject.name == "自立":
                    current_jiritsu += 1
        
        print(f"  現在の自立活動: {current_jiritsu}時間")
        needed = required_hours - current_jiritsu
        
        if needed <= 0:
            print("  → 既に必要時間を満たしています")
            continue
        
        print(f"  → あと{needed}時間必要")
        
        # 配置可能なスロットを探す
        placement_candidates = []
        
        for day in days:
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                
                # 固定科目スロットはスキップ
                if slot.day == "月" and slot.period == 6:
                    continue  # 欠
                if slot.day in ["火", "水", "金"] and slot.period == 6:
                    continue  # YT
                if slot.day == "木" and slot.period == 4:
                    continue  # 道徳
                
                # 交流学級が空いているか確認
                exchange_assignment = schedule.get_assignment(slot, exchange_ref)
                if exchange_assignment:
                    continue  # 既に配置済み
                
                # 親学級の現在の科目を確認
                parent_assignment = schedule.get_assignment(slot, parent_ref)
                if not parent_assignment:
                    continue  # 親学級も空き
                
                # 親学級が数学・英語でない場合、スワップ候補として記録
                if parent_assignment.subject.name not in ["数", "英"]:
                    # この科目を他の場所に移せるか確認
                    placement_candidates.append({
                        'slot': slot,
                        'current_subject': parent_assignment.subject.name,
                        'current_teacher': parent_assignment.teacher
                    })
        
        print(f"  配置候補スロット: {len(placement_candidates)}個")
        
        # 最初のN個の候補を使って自立活動を配置
        placed = 0
        for candidate in placement_candidates[:needed]:
            slot = candidate['slot']
            current_subject = candidate['current_subject']
            
            print(f"\n  {slot}に自立活動を配置:")
            print(f"    親学級の現在の科目: {current_subject}")
            
            # 親学級の科目を数学に変更
            parent_assignment = schedule.get_assignment(slot, parent_ref)
            if parent_assignment:
                schedule.remove_assignment(slot, parent_ref)
            
            math_teacher = school.get_assigned_teacher(Subject("数"), parent_ref)
            if math_teacher:
                math_assignment = Assignment(parent_ref, Subject("数"), math_teacher)
                schedule.assign(slot, math_assignment)
                print(f"    → 親学級を数学に変更")
            
            # 交流学級に自立活動を配置
            jiritsu_teacher = None
            for subject in school.get_required_subjects(exchange_ref):
                if subject.name == "自立":
                    jiritsu_teacher = school.get_assigned_teacher(subject, exchange_ref)
                    break
            
            if jiritsu_teacher:
                jiritsu_assignment = Assignment(exchange_ref, Subject("自立"), jiritsu_teacher)
                schedule.assign(slot, jiritsu_assignment)
                print(f"    → 交流学級に自立活動を配置")
                placed += 1
                fixed_count += 1
        
        print(f"\n  結果: {placed}時間の自立活動を配置")
    
    # 保存
    if fixed_count > 0:
        output_path = base_path / "output" / "output.csv"
        schedule_repo.save_schedule(schedule, "output.csv")
        print(f"\n合計{fixed_count}個の自立活動を配置しました")
        print(f"結果を{output_path}に保存しました")
    else:
        print("\n修正は必要ありませんでした")

if __name__ == "__main__":
    main()