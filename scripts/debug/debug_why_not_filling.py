#!/usr/bin/env python3
"""なぜ3年生の6限目が埋まらないかデバッグするスクリプト"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.application.services.data_loading_service import DataLoadingService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

def main():
    # サービスの初期化
    data_loading_service = DataLoadingService()
    data_dir = Path("data")
    
    # 学校データ読み込み
    school, use_enhanced_features = data_loading_service.load_school_data(data_dir)
    
    # 最新の時間割を読み込み
    csv_repo = CSVScheduleRepository()
    schedule = csv_repo.load_desired_schedule("data/output/output.csv", school)
    
    print("=== 3年生6限目が埋まらない理由を調査 ===\n")
    
    # SmartEmptySlotFillerRefactoredの_should_skip_slotロジックを確認
    # 3年3組の月曜6限をチェック
    time_slot = TimeSlot("月", 6)
    class_ref = ClassReference(3, 3)
    
    print(f"調査対象: {class_ref.full_name} {time_slot}")
    
    # _should_skip_slotメソッドのロジックを直接実装してチェック
    # 3年生の特別ルール：月曜・火曜・水曜の6限は授業可能
    if class_ref.grade == 3:
        # 金曜6限のYTのみスキップ
        if time_slot.day == "金" and time_slot.period == 6:
            should_skip = True
        else:
            should_skip = False
    else:
        # 1・2年生のルール
        if time_slot.day == "月" and time_slot.period == 6:
            should_skip = True
        elif ((time_slot.day == "火" and time_slot.period == 6) or
              (time_slot.day == "水" and time_slot.period == 6) or
              (time_slot.day == "金" and time_slot.period == 6)):
            should_skip = True
        else:
            should_skip = False
    
    print(f"スキップ判定: {should_skip}")
    
    # 現在の割り当てを確認
    assignment = schedule.get_assignment(time_slot, class_ref)
    if assignment:
        print(f"現在の割り当て: {assignment.subject.name} ({assignment.teacher.name})")
    else:
        print("現在の割り当て: なし")
    
    # ロック状態を確認
    is_locked = schedule.is_locked(time_slot, class_ref)
    print(f"ロック状態: {is_locked}")
    
    # 空きスロットをチェック
    print("\n=== 3年生の月火水6限の状況 ===")
    days = ["月", "火", "水"]
    third_grade_classes = [
        ClassReference(3, 1),
        ClassReference(3, 2),
        ClassReference(3, 3),
        ClassReference(3, 5),
        ClassReference(3, 6),
        ClassReference(3, 7)
    ]
    
    for day in days:
        print(f"\n{day}曜日6限:")
        ts = TimeSlot(day, 6)
        for cr in third_grade_classes:
            assignment = schedule.get_assignment(ts, cr)
            locked = schedule.is_locked(ts, cr)
            if assignment:
                print(f"  {cr.full_name}: {assignment.subject.name} (ロック: {locked})")
            else:
                print(f"  {cr.full_name}: [空き] (ロック: {locked})")

if __name__ == "__main__":
    main()