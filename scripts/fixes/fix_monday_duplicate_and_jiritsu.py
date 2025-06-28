#!/usr/bin/env python3
"""月曜日の2年2組の日内重複と交流学級の自立活動違反を修正するスクリプト"""
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


def main():
    """月曜日の2年2組の日内重複と交流学級の自立活動違反を修正"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 問題1: 2年2組の月曜日の社会重複を修正
    logger.info("\n=== 問題1: 2年2組の月曜日の社会重複を修正 ===")
    
    class_ref = ClassReference(2, 2)
    
    # 月曜日の授業を確認
    monday_subjects = {}
    for period in range(1, 7):
        time_slot = TimeSlot("月", period)
        assignment = schedule.get_assignment(time_slot, class_ref)
        if assignment:
            logger.info(f"月曜{period}限: {assignment.subject.name}")
            if assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
                monday_subjects[period] = assignment
    
    # 社会の重複を確認（3限と5限）
    if 3 in monday_subjects and 5 in monday_subjects:
        if monday_subjects[3].subject.name == "社" and monday_subjects[5].subject.name == "社":
            logger.info("\n月曜3限と5限に社会が重複しています")
            
            # 月曜5限を他の科目に変更
            target_slot = TimeSlot("月", 5)
            schedule.remove_assignment(target_slot, class_ref)
            
            # 不足している科目を探す
            needed_subjects = ["英", "国", "理", "音", "美", "家", "技"]
            
            replaced = False
            for subject_name in needed_subjects:
                subject = Subject(subject_name)
                teacher = school.get_assigned_teacher(subject, class_ref)
                
                if teacher:
                    # 教師が利用可能か確認
                    teacher_available = True
                    for other_class in school.get_all_classes():
                        if other_class == class_ref:
                            continue
                        other_assignment = schedule.get_assignment(target_slot, other_class)
                        if other_assignment and other_assignment.teacher == teacher:
                            teacher_available = False
                            break
                    
                    if teacher_available:
                        new_assignment = Assignment(class_ref, subject, teacher)
                        if schedule.assign(target_slot, new_assignment):
                            logger.info(f"✓ 月曜5限: 社 → {subject_name}({teacher.name})")
                            replaced = True
                            break
    
    # 問題2: 交流学級の自立活動違反を修正
    logger.info("\n=== 問題2: 交流学級の自立活動違反を修正 ===")
    
    # 違反パターンを検出
    violations = []
    
    # 2年7組（交流）の月曜5限：自立 → 2年2組（親）の月曜5限：新しく配置された科目をチェック
    exchange_pairs = [
        (ClassReference(2, 7), ClassReference(2, 2), TimeSlot("月", 5)),
        (ClassReference(3, 6), ClassReference(3, 3), TimeSlot("金", 5))
    ]
    
    for exchange_class, parent_class, time_slot in exchange_pairs:
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        if exchange_assignment and parent_assignment:
            if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                if parent_assignment.subject.name not in ["数", "英", "算"]:
                    violations.append({
                        'time_slot': time_slot,
                        'exchange_class': exchange_class,
                        'parent_class': parent_class,
                        'exchange_subject': exchange_assignment.subject.name,
                        'parent_subject': parent_assignment.subject.name
                    })
    
    logger.info(f"\n発見された違反: {len(violations)}件")
    for v in violations:
        logger.info(f"{v['time_slot']}: {v['exchange_class'].full_name}({v['exchange_subject']}) " +
                   f"← {v['parent_class'].full_name}({v['parent_subject']})")
    
    # 違反を修正
    for violation in violations:
        time_slot = violation['time_slot']
        parent_class = violation['parent_class']
        
        logger.info(f"\n{time_slot} {parent_class.full_name}の{violation['parent_subject']}を修正中...")
        
        # 親学級を数学または英語に変更
        schedule.remove_assignment(time_slot, parent_class)
        
        # まず数学を試す
        for subject_name in ["数", "英"]:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, parent_class)
            
            if teacher:
                # 教師が利用可能か確認
                teacher_available = True
                for other_class in school.get_all_classes():
                    if other_class == parent_class:
                        continue
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and other_assignment.teacher == teacher:
                        teacher_available = False
                        break
                
                # その日に既に同じ科目があるかチェック
                day_subjects = []
                for period in range(1, 7):
                    if period == time_slot.period:
                        continue
                    check_slot = TimeSlot(time_slot.day, period)
                    check_assignment = schedule.get_assignment(check_slot, parent_class)
                    if check_assignment:
                        day_subjects.append(check_assignment.subject.name)
                
                if subject_name not in day_subjects and teacher_available:
                    new_assignment = Assignment(parent_class, subject, teacher)
                    if schedule.assign(time_slot, new_assignment):
                        logger.info(f"✓ {parent_class.full_name}: {violation['parent_subject']} → {subject_name}({teacher.name})")
                        break
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    
    # 2年2組の月曜日の重複確認
    logger.info("\n2年2組の月曜日:")
    mon_subjects = {}
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("月", period), ClassReference(2, 2))
        if assignment and assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
            subject_name = assignment.subject.name
            mon_subjects[subject_name] = mon_subjects.get(subject_name, 0) + 1
            logger.info(f"  {period}限: {subject_name}")
    
    for subject, count in mon_subjects.items():
        if count > 1:
            logger.warning(f"  → {subject}が{count}回 - まだ重複!")
        else:
            logger.info(f"  → {subject}: {count}回 ✓")
    
    # 交流学級の自立活動確認
    logger.info("\n交流学級の自立活動:")
    for exchange_class, parent_class, time_slot in exchange_pairs:
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        if exchange_assignment and parent_assignment:
            if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                status = "✓" if parent_assignment.subject.name in ["数", "英", "算"] else "✗"
                logger.info(f"  {time_slot} {exchange_class.full_name}(自立) ← " +
                           f"{parent_class.full_name}({parent_assignment.subject.name}) {status}")


if __name__ == "__main__":
    main()