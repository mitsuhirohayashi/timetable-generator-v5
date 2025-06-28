#!/usr/bin/env python3
"""教師割り当ての分析スクリプト"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from collections import defaultdict

def main():
    # リポジトリの初期化
    school_repo = CSVSchoolRepository(Path("data"))
    schedule_repo = CSVScheduleRepository(Path("data"))
    
    # 学校データとスケジュールの読み込み
    print("=== データ読み込み ===")
    school = school_repo.load_school_data("config/base_timetable.csv")
    schedule = schedule_repo.load_desired_schedule("output/output.csv", school)
    
    # 教師ごとの割り当てを集計
    teacher_assignments = defaultdict(list)
    subject_teacher_mapping = defaultdict(set)
    
    print("\n=== 教師割り当ての分析 ===")
    
    days = ["月", "火", "水", "木", "金"]
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    teacher_name = assignment.teacher.name
                    subject_name = assignment.subject.name
                    
                    # 教師ごとの割り当てを記録
                    teacher_assignments[teacher_name].append(
                        f"{day}{period} {class_ref}: {subject_name}"
                    )
                    
                    # 教科と教師のマッピングを記録
                    subject_teacher_mapping[subject_name].add(teacher_name)
    
    # 結果の表示
    print("\n=== 教師別の担当授業数 ===")
    for teacher, assignments in sorted(teacher_assignments.items()):
        if teacher != "欠課":  # 欠課は除外
            print(f"{teacher}: {len(assignments)}コマ")
    
    print("\n=== 教科別の担当教師 ===")
    for subject, teachers in sorted(subject_teacher_mapping.items()):
        if subject not in ["欠", "YT", "道", "学", "総", "行"]:  # 固定科目は除外
            teacher_list = ", ".join(sorted(teachers))
            print(f"{subject}: {teacher_list}")
    
    # 汎用的な教師名のチェック
    print("\n=== 汎用的な教師名のチェック ===")
    generic_teachers = [t for t in teacher_assignments.keys() if "担当" in t]
    if generic_teachers:
        print(f"汎用的な教師名が見つかりました: {generic_teachers}")
        for teacher in generic_teachers[:3]:  # 最初の3件を詳細表示
            print(f"\n{teacher}の割り当て（最初の5件）:")
            for assignment in teacher_assignments[teacher][:5]:
                print(f"  {assignment}")
    else:
        print("汎用的な教師名は見つかりませんでした。全て実名の教師が割り当てられています。")
    
    # サンプル表示
    print("\n=== サンプル割り当て（最初の20件） ===")
    count = 0
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            for class_ref in school.get_all_classes()[:3]:  # 最初の3クラスのみ
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and count < 20:
                    print(f"{day}{period} {class_ref}: {assignment.subject.name} → {assignment.teacher.name}")
                    count += 1

if __name__ == "__main__":
    main()