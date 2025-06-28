#!/usr/bin/env python3
"""教師重複の詳細チェック"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_config import path_config

# リポジトリを直接作成
school_repo = CSVSchoolRepository(path_config.data_dir)
school = school_repo.load_school_data("config/base_timetable.csv")
schedule_repo = CSVScheduleRepository(path_config.data_dir)

# output.csvを読み込み
schedule = schedule_repo.load("data/output/output.csv", school)

# テスト期間
test_periods = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

print("=== 教師重複の詳細チェック ===")

# 各時間帯の教師配置を収集
from src.domain.value_objects.time_slot import TimeSlot
for day in ["月", "火", "水", "木", "金"]:
    for period in range(1, 7):
        time_slot = TimeSlot(day, period)
        
        # テスト期間はスキップ
        if (day, period) in test_periods:
            continue
        
        # この時間の教師配置
        teacher_assignments = defaultdict(list)
        
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher:
                teacher_assignments[assignment.teacher.name].append((class_ref, assignment.subject.name))
        
        # 重複をチェック
        for teacher_name, classes in teacher_assignments.items():
            if len(classes) > 1:
                # 5組の合同授業は除外
                grade5_classes = [c for c, _ in classes if c.class_number == 5]
                if len(grade5_classes) == len(classes) and len(grade5_classes) > 0:
                    continue
                
                print(f"\n{day}{period}限: {teacher_name}先生が重複")
                for class_ref, subject in classes:
                    print(f"  - {class_ref}: {subject}")
                
                # 対策案を提示
                print("  対策案:")
                for i, (class_ref, subject) in enumerate(classes):
                    if i > 0:  # 最初のクラス以外
                        # 代替教師を探す
                        alt_teachers = []
                        for t in school.get_all_teachers():
                            if t.name != teacher_name and subject in [s.name for s in school.get_subjects_for_teacher(t)]:
                                # この時間に空いているか確認
                                is_free = True
                                for c in school.get_all_classes():
                                    a = schedule.get_assignment(time_slot, c)
                                    if a and a.teacher and a.teacher.name == t.name:
                                        is_free = False
                                        break
                                if is_free:
                                    alt_teachers.append(t.name)
                        
                        if alt_teachers:
                            print(f"    {class_ref}の{subject}を他の教師に変更: {', '.join(alt_teachers[:3])}")
                        else:
                            print(f"    {class_ref}の{subject}を他の時間に移動")