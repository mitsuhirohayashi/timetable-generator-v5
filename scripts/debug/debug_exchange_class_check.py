#!/usr/bin/env python3
"""交流学級制約の詳細デバッグ"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.services.exchange_class_service import ExchangeClassService

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    exchange_service = ExchangeClassService()
    
    time_slot = TimeSlot("火", 6)
    
    # 3年3組と3年6組を取得
    class_3_3 = None
    class_3_6 = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 3:
            class_3_3 = class_ref
        elif class_ref.grade == 3 and class_ref.class_number == 6:
            class_3_6 = class_ref
    
    print(f"=== 交流学級関係の確認 ===")
    print(f"3年3組は親学級？: {exchange_service.is_parent_class(class_3_3)}")
    print(f"3年6組は交流学級？: {exchange_service.is_exchange_class(class_3_6)}")
    
    # 親学級と交流学級の対応関係を確認
    if exchange_service.is_parent_class(class_3_3):
        exchange_class = exchange_service.get_exchange_class(class_3_3)
        print(f"3年3組の交流学級: {exchange_class}")
    
    if exchange_service.is_exchange_class(class_3_6):
        parent_class = exchange_service.get_parent_class(class_3_6)
        print(f"3年6組の親学級: {parent_class}")
    
    print(f"\n=== {time_slot}の状況 ===")
    
    # 3年3組の火曜6限
    assignment_3_3 = output_schedule.get_assignment(time_slot, class_3_3)
    if assignment_3_3:
        print(f"3年3組: {assignment_3_3.subject.name} ({assignment_3_3.teacher.name if assignment_3_3.teacher else '教師未設定'})")
    else:
        print(f"3年3組: 空き")
    
    # 3年6組の火曜6限
    assignment_3_6 = output_schedule.get_assignment(time_slot, class_3_6)
    if assignment_3_6:
        print(f"3年6組: {assignment_3_6.subject.name} ({assignment_3_6.teacher.name if assignment_3_6.teacher else '教師未設定'})")
    else:
        print(f"3年6組: 空き")
    
    # 配置可能性をチェック
    print(f"\n=== 配置可能性チェック ===")
    
    # 3年3組に各科目を配置できるかチェック
    subjects_to_check = ["数", "英", "国", "理", "社", "音", "美", "技", "家"]
    
    for subject_name in subjects_to_check:
        from src.domain.value_objects.time_slot import Subject
        subject = Subject(subject_name)
        can_place = exchange_service.can_place_subject_for_parent_class(
            output_schedule, time_slot, class_3_3, subject
        )
        print(f"{subject_name}を3年3組に配置可能？: {can_place}")
        
        # もし配置不可の場合、交流学級の状況を確認
        if not can_place and exchange_class:
            exchange_assignment = output_schedule.get_assignment(time_slot, exchange_class)
            if exchange_assignment:
                print(f"  → 交流学級{exchange_class}の科目: {exchange_assignment.subject.name}")

if __name__ == "__main__":
    main()