#!/usr/bin/env python3
"""教師重複違反の確認スクリプト"""

import pandas as pd
from src.domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
from src.domain.entities.school import School, Teacher
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment, ClassReference
import os

# スケジュールを読み込む
print("=== 教師重複違反チェック ===\n")

# CSVから時間割データを読み込む
csv_reader = CSVScheduleRepository()
output_path = os.path.join(path_config.data_dir, 'output', 'output.csv')
schedule = csv_reader.load(output_path)

# 教師マッピングデータを読み込む
teacher_df = pd.read_csv('data/config/teacher_subject_mapping.csv')

# 教師オブジェクトを作成
teachers = {}
for _, row in teacher_df.iterrows():
    teacher_name = row['教員名']
    if teacher_name not in teachers:
        teachers[teacher_name] = Teacher(teacher_name)

# 学校オブジェクトを作成
school = School()
for teacher in teachers.values():
    school.add_teacher(teacher)

# 教師重複制約をチェック
constraint = TeacherConflictConstraint()
result = constraint.validate(schedule, school)

print(f"教師重複違反数: {len(result.violations)}\n")

# 井上先生と北先生の違反のみ表示
for violation in result.violations:
    if '井上' in violation.description or '北' in violation.description:
        print(f"- {violation.description}")
        print(f"  時間: {violation.time_slot}")
        print()

# 詳細分析
print("\n=== 詳細分析 ===")

# 月曜5限の状況
print("\n1. 月曜5限の社会科:")
time_slot = TimeSlot("月", 5)
class_3_2 = ClassReference(3, 2)
class_3_3 = ClassReference(3, 3)

assignment_3_2 = schedule.get_assignment(time_slot, class_3_2)
assignment_3_3 = schedule.get_assignment(time_slot, class_3_3)

if assignment_3_2:
    print(f"  3年2組: {assignment_3_2.subject.name} ({assignment_3_2.teacher.name if assignment_3_2.teacher else '教師未定'})")
if assignment_3_3:
    print(f"  3年3組: {assignment_3_3.subject.name} ({assignment_3_3.teacher.name if assignment_3_3.teacher else '教師未定'})")

# 火曜5限の状況
print("\n2. 火曜5限の数学:")
time_slot = TimeSlot("火", 5)
class_2_1 = ClassReference(2, 1)
class_2_2 = ClassReference(2, 2)

assignment_2_1 = schedule.get_assignment(time_slot, class_2_1)
assignment_2_2 = schedule.get_assignment(time_slot, class_2_2)

if assignment_2_1:
    print(f"  2年1組: {assignment_2_1.subject.name} ({assignment_2_1.teacher.name if assignment_2_1.teacher else '教師未定'})")
if assignment_2_2:
    print(f"  2年2組: {assignment_2_2.subject.name} ({assignment_2_2.teacher.name if assignment_2_2.teacher else '教師未定'})")