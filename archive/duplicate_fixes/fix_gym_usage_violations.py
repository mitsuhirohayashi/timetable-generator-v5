#!/usr/bin/env python3
"""体育館使用違反を修正するスクリプト

体育館は1つしかないため、同じ時間に複数のクラスが保健体育を実施することはできません。
ただし、5組（1-5, 2-5, 3-5）の合同体育は例外として許可されます。
"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import PathConfig
from src.infrastructure.parsers.basics_parser import BasicsParser
from src.infrastructure.parsers.teacher_assignment_parser import TeacherAssignmentParser
from src.domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
from src.domain.services.test_period_protector import TestPeriodProtector


def find_gym_usage_violations(schedule: Schedule, school: School) -> list:
    """体育館使用違反を検出"""
    violations = []
    constraint = GymUsageConstraintRefactored()
    test_protector = TestPeriodProtector()
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # テスト期間中はスキップ
            if test_protector.is_test_period(time_slot):
                continue
            
            # この時間に保健体育を実施しているクラスを収集
            pe_classes = []
            pe_assignments = []
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == "保":
                    pe_classes.append(class_ref)
                    pe_assignments.append(assignment)
            
            # 2クラス以上が同時に保健体育を実施していて、合同体育でない場合は違反
            if len(pe_classes) > 1 and not constraint._is_joint_pe_session(pe_classes):
                violations.append({
                    'time_slot': time_slot,
                    'classes': pe_classes,
                    'assignments': pe_assignments
                })
    
    return violations


def find_alternative_slot(schedule: Schedule, school: School, class_ref: ClassReference, 
                         subject: Subject, teacher, avoid_slot: TimeSlot) -> TimeSlot:
    """代替スロットを探す"""
    test_protector = TestPeriodProtector()
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            if day == "月" and period == 6:  # 固定制約
                continue
            
            time_slot = TimeSlot(day, period)
            
            # 元のスロットと同じ場合はスキップ
            if time_slot == avoid_slot:
                continue
            
            # テスト期間中はスキップ
            if test_protector.is_test_period(time_slot):
                continue
            
            # 既に授業がある場合はスキップ
            if schedule.get_assignment(time_slot, class_ref):
                continue
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, class_ref):
                continue
            
            # 教師の可用性チェック
            if teacher and not schedule.is_teacher_available(time_slot, teacher):
                continue
            
            # 保健体育の場合は体育館使用チェック
            if subject.name == "保":
                # この時間に他のクラスが保健体育を実施していないかチェック
                pe_count = sum(
                    1 for cls in school.get_all_classes()
                    if schedule.get_assignment(time_slot, cls) and
                    schedule.get_assignment(time_slot, cls).subject.name == "保"
                )
                if pe_count > 0:
                    continue
            
            # 日内重複チェック
            same_subject_count = sum(
                1 for p in range(1, 7)
                if schedule.get_assignment(TimeSlot(day, p), class_ref) and
                schedule.get_assignment(TimeSlot(day, p), class_ref).subject == subject
            )
            if same_subject_count > 0:
                continue
            
            return time_slot
    
    return None


def fix_gym_violations(schedule: Schedule, school: School) -> int:
    """体育館使用違反を修正"""
    violations = find_gym_usage_violations(schedule, school)
    fixed_count = 0
    
    print(f"\n体育館使用違反を{len(violations)}件検出しました")
    
    for violation in violations:
        time_slot = violation['time_slot']
        classes = violation['classes']
        
        print(f"\n{time_slot}: {len(classes)}クラスが同時に保健体育を実施")
        for cls in classes:
            print(f"  - {cls}")
        
        # 最初のクラス以外を移動
        for i in range(1, len(classes)):
            class_ref = classes[i]
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if not assignment:
                continue
            
            # 代替スロットを探す
            new_slot = find_alternative_slot(schedule, school, class_ref, 
                                           assignment.subject, assignment.teacher, time_slot)
            
            if new_slot:
                # 元のスロットの授業を削除
                schedule.remove_assignment(time_slot, class_ref)
                
                # 新しいスロットに配置
                try:
                    schedule.assign(new_slot, assignment)
                    print(f"  → {class_ref}の保健体育を{time_slot}から{new_slot}に移動")
                    fixed_count += 1
                    
                    # 交流学級も同期が必要な場合は処理
                    parent_to_exchange = {
                        ClassReference(1, 1): ClassReference(1, 6),
                        ClassReference(1, 2): ClassReference(1, 7),
                        ClassReference(2, 3): ClassReference(2, 6),
                        ClassReference(2, 2): ClassReference(2, 7),
                        ClassReference(3, 3): ClassReference(3, 6),
                        ClassReference(3, 2): ClassReference(3, 7)
                    }
                    
                    if class_ref in parent_to_exchange:
                        exchange_class = parent_to_exchange[class_ref]
                        if exchange_class in school.get_all_classes():
                            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                            if exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                                # 交流学級も移動
                                schedule.remove_assignment(time_slot, exchange_class)
                                exchange_teacher = school.get_assigned_teacher(assignment.subject, exchange_class)
                                if not exchange_teacher:
                                    exchange_teacher = assignment.teacher
                                new_exchange_assignment = Assignment(exchange_class, assignment.subject, exchange_teacher)
                                try:
                                    schedule.assign(new_slot, new_exchange_assignment)
                                    print(f"  → 交流学級{exchange_class}も同期して移動")
                                except ValueError as e:
                                    print(f"  ! 交流学級{exchange_class}の同期に失敗: {e}")
                    
                except ValueError as e:
                    print(f"  ! {class_ref}の移動に失敗: {e}")
                    # 元に戻す
                    schedule.assign(time_slot, assignment)
            else:
                print(f"  ! {class_ref}の保健体育の代替スロットが見つかりません")
    
    return fixed_count


def main():
    """メイン処理"""
    # パス設定
    path_config = PathConfig()
    
    # リポジトリ初期化
    repository = CSVScheduleRepository(
        base_timetable_path=path_config.get_base_timetable_path(),
        input_dir=path_config.get_input_csv_dir(),
        output_dir=path_config.get_output_csv_dir()
    )
    
    # スケジュール読み込み
    print("スケジュールを読み込んでいます...")
    schedule = repository.load_schedule()
    
    # 学校情報の構築
    print("学校情報を構築しています...")
    basic_parser = BasicsParser(path_config.get_basics_path())
    constraints_data = basic_parser.parse()
    
    teacher_parser = TeacherAssignmentParser(
        path_config.get_teacher_assignment_path(),
        path_config.get_default_teacher_mapping_path()
    )
    teacher_assignments = teacher_parser.parse()
    
    from src.domain.entities.school import School
    school = School()
    
    # クラスと教師の登録
    all_classes = set()
    all_teachers = set()
    
    for entry in teacher_assignments.entries:
        all_classes.add(entry.class_ref)
        all_teachers.add(entry.teacher)
        school.assign_teacher_to_class(entry.class_ref, entry.subject, entry.teacher)
    
    for class_ref in all_classes:
        school.add_class(class_ref)
    
    for teacher in all_teachers:
        school.add_teacher(teacher)
    
    # 基準時数の設定
    from src.infrastructure.repositories.base_timetable_repository import BaseTimeTableRepository
    base_repo = BaseTimeTableRepository()
    base_timetable = base_repo.load_base_timetable()
    
    for class_ref in all_classes:
        if class_ref in base_timetable.entries:
            for subject, hours in base_timetable.entries[class_ref].items():
                school.set_standard_hours(class_ref, subject, hours)
    
    # 体育館使用違反を修正
    fixed_count = fix_gym_violations(schedule, school)
    
    if fixed_count > 0:
        print(f"\n合計{fixed_count}件の体育館使用違反を修正しました")
        
        # スケジュールを保存
        print("\n修正したスケジュールを保存しています...")
        repository.save_schedule(schedule)
        print("保存完了: data/output/output.csv")
    else:
        print("\n修正が必要な体育館使用違反はありませんでした")


if __name__ == "__main__":
    main()