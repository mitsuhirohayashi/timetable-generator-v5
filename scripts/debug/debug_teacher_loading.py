#!/usr/bin/env python3
"""デバッグ: 教師データの読み込みを確認"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.value_objects.time_slot import Subject, ClassReference

def main():
    # リポジトリの初期化
    school_repo = CSVSchoolRepository(Path("data"))
    teacher_mapping_repo = TeacherMappingRepository(Path("data/config"))
    
    # 教師マッピングの読み込み
    print("=== 教師マッピングの読み込み ===")
    teacher_mapping = teacher_mapping_repo.load_teacher_mapping("teacher_subject_mapping.csv")
    
    print(f"読み込まれた教師数: {len(teacher_mapping)}")
    for teacher_name, assignments in list(teacher_mapping.items())[:5]:
        print(f"\n教師: {teacher_name}")
        for subject, classes in assignments:
            print(f"  {subject.name}: {[f'{c.grade}-{c.class_number}' for c in classes]}")
    
    # 学校データの読み込み
    print("\n\n=== 学校データの読み込み ===")
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 特定のクラス・教科の教師を確認
    test_cases = [
        (ClassReference(1, 1), Subject("国")),
        (ClassReference(1, 1), Subject("数")),
        (ClassReference(1, 1), Subject("英")),
        (ClassReference(2, 2), Subject("理")),
        (ClassReference(1, 5), Subject("美")),
    ]
    
    print("\n=== 教師割り当ての確認 ===")
    for class_ref, subject in test_cases:
        teacher = school.get_assigned_teacher(subject, class_ref)
        if teacher:
            print(f"{class_ref} {subject.name}: {teacher.name}")
        else:
            # teacher_mapping_repoから直接取得してみる
            direct_teacher = teacher_mapping_repo.get_teacher_for_subject_class(
                teacher_mapping, subject, class_ref
            )
            if direct_teacher:
                print(f"{class_ref} {subject.name}: ✗ 学校に未登録 (マッピングには存在: {direct_teacher.name})")
            else:
                print(f"{class_ref} {subject.name}: ✗ 教師未割り当て")
    
    # CSVリーダーをテスト
    print("\n\n=== CSVリーダーのテスト ===")
    from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
    schedule_repo = CSVScheduleRepository(Path("data"))
    
    # 小さなテストスケジュールを読み込み
    try:
        schedule = schedule_repo.load_desired_schedule("input/input.csv", school)
        
        # 最初の数件の割り当てをチェック
        print("\n読み込まれた割り当て（最初の10件）:")
        count = 0
        days = ["月", "火", "水", "木", "金"]
        from src.domain.value_objects.time_slot import TimeSlot
        for day in days:
            for period in range(1, 7):
                for class_ref in [ClassReference(1, 1), ClassReference(1, 2)]:
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and count < 10:
                        print(f"  {day}{period} {class_ref}: {assignment.subject.name} - {assignment.teacher.name}")
                        count += 1
                        
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    main()