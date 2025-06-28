#!/usr/bin/env python3
"""教師重複違反を高度な交換アルゴリズムで修正"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict
import random

def find_teacher_conflicts(schedule, school):
    """教師の重複を検出"""
    conflicts = []
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = defaultdict(list)
            
            # この時間の全ての教師割り当てを収集
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_assignments[assignment.teacher.name].append((class_ref, assignment))
            
            # 重複を検出
            for teacher_name, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
                    is_grade5_joint = all(class_ref in grade5_classes for class_ref, _ in assignments)
                    
                    if not is_grade5_joint:
                        conflicts.append({
                            'time_slot': time_slot,
                            'teacher': teacher_name,
                            'assignments': assignments
                        })
    
    return conflicts

def can_swap_assignments(schedule, school, slot1, class1, slot2, class2):
    """2つの授業を交換可能かチェック"""
    # ロックチェック
    if schedule.is_locked(slot1, class1) or schedule.is_locked(slot2, class2):
        return False
    
    # 授業を取得
    assignment1 = schedule.get_assignment(slot1, class1)
    assignment2 = schedule.get_assignment(slot2, class2)
    
    # 両方とも授業がある必要がある
    if not assignment1 or not assignment2:
        return False
    
    # 同じ科目の場合は交換しても意味がない
    if assignment1.subject.name == assignment2.subject.name:
        return False
    
    # 固定科目は交換しない
    fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
    if assignment1.subject.name in fixed_subjects or assignment2.subject.name in fixed_subjects:
        return False
    
    return True

def find_swap_candidate(schedule, school, conflict_time_slot, conflict_class, conflict_teacher):
    """交換候補を探す"""
    candidates = []
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # 同じ時間は除外
            if time_slot == conflict_time_slot:
                continue
            
            # この時間に教師が空いているかチェック
            teacher_busy = False
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == conflict_teacher:
                    teacher_busy = True
                    break
            
            if not teacher_busy:
                # 交換可能な授業を探す
                current_assignment = schedule.get_assignment(time_slot, conflict_class)
                if current_assignment and can_swap_assignments(
                    schedule, school, conflict_time_slot, conflict_class, time_slot, conflict_class
                ):
                    candidates.append({
                        'time_slot': time_slot,
                        'class_ref': conflict_class,
                        'assignment': current_assignment,
                        'priority': 1 if day == conflict_time_slot.day else 2
                    })
    
    # 優先度でソート（同じ日を優先）
    candidates.sort(key=lambda x: x['priority'])
    return candidates

def fix_teacher_conflicts_with_swapping(schedule, school):
    """教師重複を交換により修正"""
    fixed_count = 0
    max_iterations = 50
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        conflicts = find_teacher_conflicts(schedule, school)
        
        if not conflicts:
            print(f"全ての教師重複が解消されました（{iteration}回の反復）")
            break
        
        print(f"\n反復{iteration}: {len(conflicts)}件の教師重複を検出")
        
        # 各重複を処理
        progress_made = False
        for conflict in conflicts[:5]:  # 一度に5件まで処理
            time_slot = conflict['time_slot']
            teacher_name = conflict['teacher']
            assignments = conflict['assignments']
            
            print(f"\n{time_slot}: {teacher_name}先生が{len(assignments)}クラスで重複")
            
            # 最初のクラスは残し、残りを処理
            for i, (class_ref, assignment) in enumerate(assignments[1:], 1):
                # ロックされている場合はスキップ
                if schedule.is_locked(time_slot, class_ref):
                    print(f"  {class_ref}はロックされているためスキップ")
                    continue
                
                # 交換候補を探す
                swap_candidates = find_swap_candidate(
                    schedule, school, time_slot, class_ref, teacher_name
                )
                
                if swap_candidates:
                    # 最初の候補と交換
                    candidate = swap_candidates[0]
                    swap_slot = candidate['time_slot']
                    
                    # 交換実行
                    assignment1 = schedule.get_assignment(time_slot, class_ref)
                    assignment2 = schedule.get_assignment(swap_slot, class_ref)
                    
                    schedule.remove_assignment(time_slot, class_ref)
                    schedule.remove_assignment(swap_slot, class_ref)
                    
                    schedule.assign(time_slot, assignment2)
                    schedule.assign(swap_slot, assignment1)
                    
                    print(f"  {class_ref}: {time_slot}の{assignment1.subject.name}と{swap_slot}の{assignment2.subject.name}を交換")
                    fixed_count += 1
                    progress_made = True
                else:
                    print(f"  {class_ref}の交換候補が見つかりません")
        
        if not progress_made:
            print("\n進展がないため、より高度な解決策を試みます...")
            # 複数の授業を連鎖的に交換する処理をここに追加できる
            break
    
    return fixed_count

def fix_daily_duplicates(schedule, school):
    """日内重複を修正"""
    fixed_count = 0
    
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            # その日の科目をカウント
            subject_slots = defaultdict(list)
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subject_slots[assignment.subject.name].append((time_slot, assignment))
            
            # 重複をチェック
            for subject_name, slots in subject_slots.items():
                if len(slots) > 1:
                    # 固定科目は除外
                    if subject_name in {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}:
                        continue
                    
                    print(f"\n{class_ref}の{day}曜日に{subject_name}が{len(slots)}回重複")
                    
                    # 2つ目以降を他の日に移動
                    for i, (dup_slot, dup_assignment) in enumerate(slots[1:], 1):
                        if schedule.is_locked(dup_slot, class_ref):
                            continue
                        
                        # 他の日で空きスロットを探す
                        moved = False
                        for other_day in ["月", "火", "水", "木", "金"]:
                            if other_day == day:
                                continue
                            
                            for other_period in range(1, 7):
                                other_slot = TimeSlot(other_day, other_period)
                                
                                if not schedule.get_assignment(other_slot, class_ref):
                                    # 空きスロットに移動
                                    schedule.remove_assignment(dup_slot, class_ref)
                                    schedule.assign(other_slot, dup_assignment)
                                    print(f"  {dup_slot}から{other_slot}に移動")
                                    fixed_count += 1
                                    moved = True
                                    break
                            
                            if moved:
                                break
    
    return fixed_count

def main():
    print("=== 教師重複違反修正スクリプト（高度版） ===\n")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.output_dir)
    schedule = schedule_repo.load_desired_schedule("output.csv", school)
    
    # 教師重複を修正
    print("教師重複違反を修正中...")
    teacher_fixed = fix_teacher_conflicts_with_swapping(schedule, school)
    print(f"\n教師重複: {teacher_fixed}件修正")
    
    # 日内重複を修正
    print("\n日内重複違反を修正中...")
    daily_fixed = fix_daily_duplicates(schedule, school)
    print(f"\n日内重複: {daily_fixed}件修正")
    
    print(f"\n合計{teacher_fixed + daily_fixed}件の違反を修正しました")
    
    # 結果を保存
    writer = CSVScheduleWriterImproved()
    writer.write(schedule, path_config.output_dir / "output.csv")
    
    print("\n修正結果をoutput.csvに保存しました")
    
    # 最終チェック
    final_conflicts = find_teacher_conflicts(schedule, school)
    if final_conflicts:
        print(f"\n警告: まだ{len(final_conflicts)}件の教師重複が残っています")
        for conflict in final_conflicts[:5]:
            print(f"  {conflict['time_slot']}: {conflict['teacher']}先生")
    else:
        print("\n✓ 全ての教師重複が解消されました")

if __name__ == "__main__":
    main()