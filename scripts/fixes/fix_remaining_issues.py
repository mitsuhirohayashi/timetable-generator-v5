#!/usr/bin/env python3
"""残っている問題を修正するスクリプト
1. 2年2組の火曜5限の社会（蒲地）を他の科目と入れ替える
2. 3年3組の木曜の数学重複を解消する
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import get_path_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_swappable_slot(schedule, school, class_ref, subject_to_find, avoid_day=None, avoid_teacher=None):
    """指定された科目で、交換可能なスロットを探す"""
    for day in ["月", "火", "水", "木", "金"]:
        if day == avoid_day:
            continue
            
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, class_ref):
                continue
                
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject_to_find:
                # 避けるべき教師の場合はスキップ
                if avoid_teacher and assignment.teacher.name == avoid_teacher:
                    continue
                    
                return time_slot, assignment
    
    return None, None


def main():
    """残っている問題を修正"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 問題1: 2年2組の火曜5限の社会（蒲地）を修正
    logger.info("\n=== 問題1: 2年2組の火曜5限の社会（蒲地）を修正 ===")
    
    class_ref = ClassReference(2, 2)
    problem_slot = TimeSlot("火", 5)
    
    # 火曜5限の現在の割り当てを確認
    current_assignment = schedule.get_assignment(problem_slot, class_ref)
    if current_assignment and current_assignment.subject.name == "社" and current_assignment.teacher.name == "蒲地":
        logger.info(f"問題発見: {class_ref.full_name} {problem_slot} - {current_assignment.subject.name}({current_assignment.teacher.name})")
        
        # 他の日の社会以外の科目で交換可能なものを探す
        swap_candidates = ["英", "国", "数", "理", "音", "美", "保", "技", "家"]
        
        swapped = False
        for swap_subject in swap_candidates:
            swap_slot, swap_assignment = find_swappable_slot(schedule, school, class_ref, swap_subject, avoid_day="火")
            
            if swap_slot and swap_assignment:
                # その時間に蒲地先生が空いているか確認
                kamachi_available = True
                for other_class in school.get_all_classes():
                    if other_class == class_ref:
                        continue
                    other_assignment = schedule.get_assignment(swap_slot, other_class)
                    if other_assignment and other_assignment.teacher.name == "蒲地":
                        kamachi_available = False
                        break
                
                # 火曜5限にswap_assignmentの教師が空いているか確認
                swap_teacher_available = True
                for other_class in school.get_all_classes():
                    if other_class == class_ref:
                        continue
                    other_assignment = schedule.get_assignment(problem_slot, other_class)
                    if other_assignment and other_assignment.teacher == swap_assignment.teacher:
                        swap_teacher_available = False
                        break
                
                if kamachi_available and swap_teacher_available:
                    # 交換を実行
                    schedule.remove_assignment(problem_slot, class_ref)
                    schedule.remove_assignment(swap_slot, class_ref)
                    
                    # 火曜5限に元のswap_slotの科目を配置
                    new_assignment1 = Assignment(class_ref, swap_assignment.subject, swap_assignment.teacher)
                    schedule.assign(problem_slot, new_assignment1)
                    
                    # swap_slotに社会を配置
                    new_assignment2 = Assignment(class_ref, current_assignment.subject, current_assignment.teacher)
                    schedule.assign(swap_slot, new_assignment2)
                    
                    logger.info(f"✓ 交換完了: {problem_slot}の{current_assignment.subject.name} ↔ {swap_slot}の{swap_assignment.subject.name}")
                    swapped = True
                    break
        
        if not swapped:
            logger.warning("✗ 適切な交換相手が見つかりませんでした")
    
    # 問題2: 3年3組の木曜の数学重複を修正
    logger.info("\n=== 問題2: 3年3組の木曜の数学重複を修正 ===")
    
    class_ref = ClassReference(3, 3)
    
    # 木曜の授業を確認
    thu_assignments = {}
    for period in range(1, 7):
        time_slot = TimeSlot("木", period)
        assignment = schedule.get_assignment(time_slot, class_ref)
        if assignment:
            thu_assignments[period] = assignment
            logger.info(f"木曜{period}限: {assignment.subject.name}")
    
    # 数学が2回ある場合、4限の数学を他の科目に変更
    if 2 in thu_assignments and 4 in thu_assignments:
        if thu_assignments[2].subject.name == "数" and thu_assignments[4].subject.name == "数":
            logger.info("\n木曜2限と4限に数学が重複しています")
            
            # 木曜4限を変更
            target_slot = TimeSlot("木", 4)
            schedule.remove_assignment(target_slot, class_ref)
            
            # 不足している科目で交換
            needed_subjects = ["理", "国", "英", "美", "音", "技", "家"]
            
            replaced = False
            for subject_name in needed_subjects:
                # その科目が他の曜日にあるか確認（交換用）
                swap_slot, swap_assignment = find_swappable_slot(schedule, school, class_ref, subject_name)
                
                if swap_slot and swap_assignment:
                    # 木曜4限にその教師が空いているか確認
                    teacher_available = True
                    for other_class in school.get_all_classes():
                        if other_class == class_ref:
                            continue
                        other_assignment = schedule.get_assignment(target_slot, other_class)
                        if other_assignment and other_assignment.teacher == swap_assignment.teacher:
                            teacher_available = False
                            break
                    
                    if teacher_available:
                        # 直接配置（数学教師が他の時間に空いていることを前提）
                        new_assignment = Assignment(class_ref, swap_assignment.subject, swap_assignment.teacher)
                        if schedule.assign(target_slot, new_assignment):
                            logger.info(f"✓ 木曜4限: 数 → {subject_name}({swap_assignment.teacher.name})")
                            replaced = True
                            break
            
            if not replaced:
                # 交換できない場合は、単純に他の科目を配置
                for subject_name in needed_subjects:
                    subject = Subject(subject_name)
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    
                    if teacher:
                        # 教師が利用可能か確認
                        teacher_available = True
                        for other_class in school.get_all_classes():
                            other_assignment = schedule.get_assignment(target_slot, other_class)
                            if other_assignment and other_assignment.teacher == teacher:
                                teacher_available = False
                                break
                        
                        if teacher_available:
                            new_assignment = Assignment(class_ref, subject, teacher)
                            if schedule.assign(target_slot, new_assignment):
                                logger.info(f"✓ 木曜4限: 数 → {subject_name}({teacher.name})")
                                replaced = True
                                break
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    
    # 2年2組の火曜5限を確認
    logger.info("\n2年2組の火曜5限:")
    assignment = schedule.get_assignment(TimeSlot("火", 5), ClassReference(2, 2))
    if assignment:
        if assignment.teacher.name == "蒲地":
            logger.warning(f"  社会(蒲地) - まだ問題あり!")
        else:
            logger.info(f"  {assignment.subject.name}({assignment.teacher.name}) ✓")
    
    # 3年3組の木曜の重複を確認
    logger.info("\n3年3組の木曜:")
    thu_subjects = {}
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("木", period), ClassReference(3, 3))
        if assignment and assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
            thu_subjects[assignment.subject.name] = thu_subjects.get(assignment.subject.name, 0) + 1
            logger.info(f"  {period}限: {assignment.subject.name}")
    
    for subject, count in thu_subjects.items():
        if count > 1:
            logger.warning(f"  → {subject}が{count}回 - まだ重複!")
        else:
            logger.info(f"  → {subject}: {count}回 ✓")


if __name__ == "__main__":
    main()