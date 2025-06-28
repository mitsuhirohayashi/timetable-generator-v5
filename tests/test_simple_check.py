#!/usr/bin/env python3
"""単純な教師チェック"""

# pathの設定
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# 必要なクラスをインポート
from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.di_container import DIContainer

# DIコンテナから学校とスケジュールを取得
container = DIContainer()
school = container.get_school()
schedule_repo = container.get_schedule_repository()

# input.csvを読み込み
schedule = schedule_repo.load_desired_schedule("input.csv", school)

print(f"初期割り当て数: {len(schedule.get_all_assignments())}")

# 最初の10個をチェック
count = 0
for i, (time_slot, assignment) in enumerate(list(schedule.get_all_assignments())[:10]):
    print(f"\n{i+1}. {time_slot.day}{time_slot.period}限 {assignment.class_ref}")
    print(f"   科目: {assignment.subject.name}")
    print(f"   教師（assignment内）: {assignment.teacher}")
    
    # schoolから教師を取得
    from src.domain.value_objects.time_slot import Subject
    subject_obj = Subject(assignment.subject.name)
    teacher = school.get_assigned_teacher(subject_obj, assignment.class_ref)
    print(f"   教師（school取得）: {teacher}")
    
    if teacher:
        count += 1

print(f"\n教師を取得できた配置: {count}/10")