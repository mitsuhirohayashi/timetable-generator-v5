#!/usr/bin/env python3
"""教師重複の簡易チェック"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import TimeSlot

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

print("=== 教師重複（テスト期間除く） ===")

duplicates = []

# 各時間帯の教師配置を収集
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
                teacher_assignments[assignment.teacher.name].append((str(class_ref), assignment.subject.name))
        
        # 重複をチェック
        for teacher_name, classes in teacher_assignments.items():
            if len(classes) > 1:
                # 5組の合同授業は除外
                grade5_count = sum(1 for c, _ in classes if "5組" in c)
                if grade5_count == len(classes) and grade5_count > 0:
                    continue
                
                duplicates.append(f"{day}{period}限: {teacher_name}先生 - " + ", ".join([f"{c}({s})" for c, s in classes]))

# 重複を表示
for dup in duplicates:
    print(dup)

print(f"\n合計 {len(duplicates)} 件の教師重複（テスト期間除く）")