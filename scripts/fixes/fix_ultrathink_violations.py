#!/usr/bin/env python3
"""Ultrathink生成結果の違反を修正するスクリプト"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository


def fix_teacher_conflicts(schedule: Schedule, school: School, teacher_mapping: Dict) -> int:
    """教師重複を修正"""
    fixed_count = 0
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = defaultdict(list)
            
            # 教師の配置状況を収集
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[assignment.teacher.name].append((class_ref, assignment))
            
            # 重複している教師を修正
            for teacher_name, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = {"1年5組", "2年5組", "3年5組"}
                    assigned_classes = set(a[0] for a in assignments)
                    
                    if assigned_classes.issubset(grade5_classes) and len(assigned_classes) == 3:
                        continue  # 5組の合同授業は正常
                    
                    # 最初のクラス以外の割り当てを削除
                    for i, (class_ref, assignment) in enumerate(assignments[1:], 1):
                        # 固定科目はスキップ
                        if assignment.subject.name in ["YT", "道", "学", "総", "欠"]:
                            continue
                            
                        # 他の教師を探す
                        subject_name = assignment.subject.name
                        available_teachers = teacher_mapping.get_teachers_for_subject(class_ref, subject_name)
                        
                        for alt_teacher_name in available_teachers:
                            if alt_teacher_name != teacher_name:
                                alt_teacher = school.get_teacher(alt_teacher_name)
                                if alt_teacher and not is_teacher_busy(schedule, school, time_slot, alt_teacher_name):
                                    # 代替教師で上書き
                                    schedule.remove_assignment(time_slot, class_ref)
                                    schedule.assign(
                                        time_slot, 
                                        class_ref, 
                                        assignment.subject,
                                        alt_teacher
                                    )
                                    fixed_count += 1
                                    print(f"修正: {time_slot} {class_ref} - {teacher_name}先生 → {alt_teacher_name}先生")
                                    break
    
    return fixed_count


def is_teacher_busy(schedule: Schedule, school: School, time_slot: TimeSlot, teacher_name: str) -> bool:
    """指定時刻に教師が忙しいかチェック"""
    for class_ref in school.get_all_classes():
        assignment = schedule.get_assignment(time_slot, class_ref)
        if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
            return True
    return False


def fix_daily_duplicates(schedule: Schedule, school: School) -> int:
    """日内重複を修正（特に交流学級の自立活動）"""
    fixed_count = 0
    days = ["月", "火", "水", "木", "金"]
    
    # 交流学級のリスト
    exchange_classes = ["1年6組", "1年7組", "2年6組", "2年7組", "3年6組", "3年7組"]
    
    for class_ref in exchange_classes:
        for day in days:
            subjects_in_day = []
            
            # その日の全授業を収集
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subjects_in_day.append((period, assignment))
            
            # 自立活動の重複をチェック
            jiritsu_periods = [(p, a) for p, a in subjects_in_day if a.subject.name == "自立"]
            
            if len(jiritsu_periods) > 1:
                # 2つ目以降の自立活動を削除
                for period, assignment in jiritsu_periods[1:]:
                    time_slot = TimeSlot(day, period)
                    schedule.remove_assignment(time_slot, class_ref)
                    fixed_count += 1
                    print(f"削除: {time_slot} {class_ref} - 重複する自立活動")
    
    return fixed_count


def fix_gym_conflicts(schedule: Schedule, school: School) -> int:
    """体育館使用競合を修正"""
    fixed_count = 0
    days = ["月", "火", "水", "木", "金"]
    
    # 交流学級と親学級のペア
    exchange_pairs = [
        ("1年1組", "1年6組"),
        ("1年2組", "1年7組"),
        ("2年3組", "2年6組"),
        ("2年2組", "2年7組"),
        ("3年3組", "3年6組"),
        ("3年2組", "3年7組")
    ]
    
    for day in days:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            pe_classes = []
            
            # 体育を行っているクラスを収集
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == "保":
                    pe_classes.append((class_ref, assignment))
            
            # 体育館使用クラスが多すぎる場合
            if len(pe_classes) > 2:  # 通常は1クラス、ペアなら2クラスまで
                # ペア以外のクラスを特定
                non_paired_classes = []
                
                for class_ref, assignment in pe_classes:
                    is_paired = False
                    for parent, exchange in exchange_pairs:
                        if class_ref in [parent, exchange]:
                            # ペアの相手も体育をやっているか確認
                            partner = exchange if class_ref == parent else parent
                            if any(c == partner for c, _ in pe_classes):
                                is_paired = True
                                break
                    
                    if not is_paired:
                        non_paired_classes.append((class_ref, assignment))
                
                # 3つ目以降のクラスの体育を移動
                if len(non_paired_classes) > 1:
                    for class_ref, assignment in non_paired_classes[1:]:
                        # 別の時間帯を探す
                        moved = False
                        for alt_day in days:
                            for alt_period in range(1, 7):
                                if alt_day == day and alt_period == period:
                                    continue
                                    
                                alt_time_slot = TimeSlot(alt_day, alt_period)
                                if not schedule.get_assignment(alt_time_slot, class_ref):
                                    # 体育館が空いているかチェック
                                    gym_free = True
                                    for other_class in school.get_all_classes():
                                        other_assignment = schedule.get_assignment(alt_time_slot, other_class)
                                        if other_assignment and other_assignment.subject.name == "保":
                                            gym_free = False
                                            break
                                    
                                    if gym_free:
                                        # 移動実行
                                        schedule.remove_assignment(time_slot, class_ref)
                                        schedule.assign(
                                            alt_time_slot,
                                            class_ref,
                                            assignment.subject,
                                            assignment.teacher
                                        )
                                        fixed_count += 1
                                        moved = True
                                        print(f"移動: {class_ref}の体育 {time_slot} → {alt_time_slot}")
                                        break
                            
                            if moved:
                                break
    
    return fixed_count


def main():
    """メイン処理"""
    print("Ultrathink生成結果の違反修正")
    print("=" * 80)
    
    # データ読み込み
    print("\nデータを読み込み中...")
    school_repo = CSVSchoolRepository()
    school = school_repo.load_school_data(str(project_root / "data" / "config"))
    
    schedule_reader = CSVScheduleReader()
    schedule = schedule_reader.read(str(project_root / "data" / "output" / "output.csv"))
    
    # 教師マッピング読み込み
    teacher_mapping_repo = TeacherMappingRepository()
    teacher_mapping = teacher_mapping_repo.load(str(project_root / "data" / "config" / "teacher_subject_mapping.csv"))
    
    # 修正実行
    print("\n修正を実行中...")
    
    # 1. 教師重複の修正
    print("\n1. 教師重複の修正...")
    teacher_fixes = fix_teacher_conflicts(schedule, school, teacher_mapping)
    print(f"  → {teacher_fixes}件修正")
    
    # 2. 日内重複の修正
    print("\n2. 日内重複の修正...")
    duplicate_fixes = fix_daily_duplicates(schedule, school)
    print(f"  → {duplicate_fixes}件修正")
    
    # 3. 体育館競合の修正
    print("\n3. 体育館競合の修正...")
    gym_fixes = fix_gym_conflicts(schedule, school)
    print(f"  → {gym_fixes}件修正")
    
    # 結果保存
    total_fixes = teacher_fixes + duplicate_fixes + gym_fixes
    print(f"\n合計 {total_fixes}件の修正を実行しました")
    
    if total_fixes > 0:
        output_path = project_root / "data" / "output" / "output_fixed.csv"
        writer = CSVScheduleWriter()
        writer.write(schedule, str(output_path))
        print(f"\n修正済み時間割を保存: {output_path}")
        
        # 元のファイルを上書き
        import shutil
        shutil.copy(str(output_path), str(project_root / "data" / "output" / "output.csv"))
        print("output.csvを更新しました")
    else:
        print("\n修正が必要な違反はありませんでした")


if __name__ == "__main__":
    main()