#!/usr/bin/env python3
"""get_assignments_by_time_slotメソッドのデバッグ"""

import logging
from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    output_schedule = schedule_repo.load("output/output.csv", school)
    
    # 火曜6限のget_assignments_by_time_slotをテスト
    time_slot = TimeSlot("火", 6)
    
    print(f"=== get_assignments_by_time_slot({time_slot}) の結果 ===\n")
    
    assignments = output_schedule.get_assignments_by_time_slot(time_slot)
    
    print(f"返された割り当て数: {len(assignments)}")
    
    # 教師別に整理
    by_teacher = {}
    no_teacher = []
    
    for assignment in assignments:
        if assignment.teacher:
            teacher_name = assignment.teacher.name
            if teacher_name not in by_teacher:
                by_teacher[teacher_name] = []
            by_teacher[teacher_name].append(assignment)
        else:
            no_teacher.append(assignment)
    
    print(f"\n教師が設定されている割り当て:")
    for teacher_name, assigns in sorted(by_teacher.items()):
        print(f"\n{teacher_name}先生:")
        for assign in assigns:
            print(f"  - {assign.class_ref}: {assign.subject.name}")
    
    if no_teacher:
        print(f"\n教師未設定の割り当て: {len(no_teacher)}件")
        for assign in no_teacher:
            print(f"  - {assign.class_ref}: {assign.subject.name}")
    
    # 井上先生の割り当てを特にチェック
    print("\n=== 井上先生の火曜6限の割り当て ===")
    inoue_assignments = []
    for assignment in assignments:
        if assignment.teacher and "井上" in assignment.teacher.name:
            inoue_assignments.append(assignment)
    
    if inoue_assignments:
        print(f"井上先生の割り当て: {len(inoue_assignments)}件")
        for assign in inoue_assignments:
            print(f"  - {assign.class_ref}: {assign.subject.name}")
    else:
        print("井上先生の割り当てはありません")

if __name__ == "__main__":
    main()