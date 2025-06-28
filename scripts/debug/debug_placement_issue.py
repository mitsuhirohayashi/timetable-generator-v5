#!/usr/bin/env python3
"""配置失敗の原因を診断"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.csp_orchestrator import CSPOrchestrator
from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.application.services.constraint_registration_service import ConstraintRegistrationService

def main():
    print("=== 配置失敗の診断 ===")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.input_dir)
    initial_schedule = schedule_repo.load_desired_schedule("input.csv", school)
    
    print(f"\n初期スケジュールの割り当て数: {len(initial_schedule.get_all_assignments())}")
    
    # 各クラスの要求時数と配置済み時数を確認
    print("\n=== 要求時数と配置済み時数 ===")
    total_required = 0
    total_placed = 0
    total_remaining = 0
    
    for class_ref in school.get_all_classes()[:3]:  # 最初の3クラスだけ表示
        print(f"\n{class_ref}:")
        standard_hours = school.get_all_standard_hours(class_ref)
        
        for subject, hours in standard_hours.items():
            required = int(hours)
            placed = 0
            
            # 配置済みの時間数をカウント
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    from src.domain.value_objects.time_slot import TimeSlot
                    time_slot = TimeSlot(day, period)
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == subject.name:
                        placed += 1
            
            remaining = required - placed
            if remaining > 0:
                print(f"  {subject.name}: 要求{required}時間, 配置済み{placed}時間, 残り{remaining}時間")
                total_remaining += remaining
            
            total_required += required
            total_placed += placed
    
    print(f"\n合計: 要求{total_required}時間, 配置済み{total_placed}時間, 残り{total_remaining}時間")
    
    # 空きスロット数を確認
    print("\n=== 空きスロット数 ===")
    empty_count = 0
    locked_count = 0
    
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                from src.domain.value_objects.time_slot import TimeSlot
                time_slot = TimeSlot(day, period)
                assignment = initial_schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    empty_count += 1
                elif initial_schedule.is_locked(time_slot, class_ref):
                    locked_count += 1
    
    print(f"空きスロット: {empty_count}")
    print(f"ロック済みスロット: {locked_count}")
    
    # 教師の可用性を確認
    print("\n=== 教師の可用性 ===")
    for subject_name in ["数", "英", "国"]:
        from src.domain.value_objects.time_slot import Subject
        subject = Subject(subject_name)
        teachers = school.get_subject_teachers(subject)
        print(f"{subject_name}: {len(teachers)}人の教師")
        for teacher in teachers[:3]:  # 最初の3人だけ表示
            print(f"  - {teacher.name}")

if __name__ == "__main__":
    main()