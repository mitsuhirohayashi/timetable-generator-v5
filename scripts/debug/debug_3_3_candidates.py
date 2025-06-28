#!/usr/bin/env python3
"""3年3組火曜6限の候補生成をデバッグ"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_manager import PathManager
from src.domain.services.implementations.fill_strategies import StrictFillStrategy

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    
    # 教師不在情報の読み込み
    path_manager = PathManager()
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    natural_result = natural_parser.parse_file("Follow-up.csv")
    
    absence_loader = TeacherAbsenceLoader()
    if natural_result["parse_success"] and natural_result.get("teacher_absences"):
        absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
    
    # SmartEmptySlotFillerRefactoredを作成
    filler = SmartEmptySlotFillerRefactored(constraint_system, absence_loader)
    
    # 3年3組を取得
    class_3_3 = None
    for class_ref in school.get_all_classes():
        if class_ref.grade == 3 and class_ref.class_number == 3:
            class_3_3 = class_ref
            break
    
    time_slot = TimeSlot("火", 6)
    
    print(f"=== {class_3_3} {time_slot} の候補生成デバッグ ===\n")
    
    # 不足科目を取得
    shortage_subjects = filler._get_shortage_subjects_prioritized(output_schedule, school, class_3_3)
    print("不足科目（優先度スコア付き）:")
    for subject, score in list(shortage_subjects.items())[:10]:
        print(f"  {subject.name}: スコア {score}")
    
    # 教師負担を計算
    teacher_loads = filler._calculate_teacher_loads(output_schedule, school)
    print("\n教師負担（上位10名）:")
    for teacher, load in sorted(teacher_loads.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {teacher}: {load}コマ")
    
    # 戦略に従って候補リストを作成
    strategy = StrictFillStrategy()
    candidates = strategy.create_candidates(
        output_schedule, school, time_slot, class_3_3, shortage_subjects, teacher_loads
    )
    
    print(f"\n生成された候補数: {len(candidates)}")
    
    if candidates:
        print("\n候補リスト（上位10件）:")
        for i, (subject, teacher) in enumerate(candidates[:10]):
            print(f"  {i+1}. {subject.name} ({teacher.name}先生)")
    else:
        print("\n候補が生成されませんでした！")
        
        # 詳細調査
        print("\n=== 詳細調査 ===")
        print("標準時数:")
        base_hours = school.get_all_standard_hours(class_3_3)
        for subject, hours in sorted(base_hours.items(), key=lambda x: x[1], reverse=True):
            print(f"  {subject.name}: {hours}時間")
        
        print("\n現在の配置数:")
        current_hours = {}
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                ts = TimeSlot(day, period)
                assignment = output_schedule.get_assignment(ts, class_3_3)
                if assignment and assignment.subject:
                    if assignment.subject.name not in current_hours:
                        current_hours[assignment.subject.name] = 0
                    current_hours[assignment.subject.name] += 1
        
        for subject_name, count in sorted(current_hours.items()):
            print(f"  {subject_name}: {count}回")

if __name__ == "__main__":
    main()