#!/usr/bin/env python3
"""3年3組の金曜5限を修正するスクリプト"""
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
    """3年3組の金曜5限を修正（空欄を数学または英語で埋める）"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 3年3組の金曜5限を確認
    class_ref = ClassReference(3, 3)
    time_slot = TimeSlot("金", 5)
    
    current_assignment = schedule.get_assignment(time_slot, class_ref)
    if current_assignment:
        logger.info(f"現在の金曜5限: {current_assignment.subject.name}")
    else:
        logger.info("金曜5限は空欄です")
        
        # 3年6組（交流学級）の金曜5限を確認
        exchange_class = ClassReference(3, 6)
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "作業"]:
            logger.info(f"3年6組の金曜5限は{exchange_assignment.subject.name}です")
            logger.info("親学級（3年3組）は数学または英語である必要があります")
            
            # 金曜日の既存の授業を確認
            friday_subjects = []
            for period in range(1, 7):
                if period == 5:
                    continue
                check_slot = TimeSlot("金", period)
                check_assignment = schedule.get_assignment(check_slot, class_ref)
                if check_assignment:
                    friday_subjects.append(check_assignment.subject.name)
            
            logger.info(f"金曜日の既存科目: {friday_subjects}")
            
            # 数学または英語を配置
            placed = False
            for subject_name in ["数", "英"]:
                if subject_name in friday_subjects:
                    logger.info(f"{subject_name}は既に金曜日にあるためスキップ")
                    continue
                
                subject = Subject(subject_name)
                teacher = school.get_assigned_teacher(subject, class_ref)
                
                if teacher:
                    # 教師が利用可能か確認
                    teacher_available = True
                    for other_class in school.get_all_classes():
                        if other_class == class_ref:
                            continue
                        other_assignment = schedule.get_assignment(time_slot, other_class)
                        if other_assignment and other_assignment.teacher == teacher:
                            teacher_available = False
                            break
                    
                    if teacher_available:
                        new_assignment = Assignment(class_ref, subject, teacher)
                        if schedule.assign(time_slot, new_assignment):
                            logger.info(f"✓ 金曜5限に{subject_name}({teacher.name})を配置しました")
                            placed = True
                            break
            
            if not placed:
                logger.warning("数学または英語を配置できませんでした")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    
    # 3年3組と3年6組の金曜5限を確認
    parent_assignment = schedule.get_assignment(time_slot, ClassReference(3, 3))
    exchange_assignment = schedule.get_assignment(time_slot, ClassReference(3, 6))
    
    if parent_assignment and exchange_assignment:
        if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
            status = "✓" if parent_assignment.subject.name in ["数", "英", "算"] else "✗"
            logger.info(f"金曜5限: 3年6組({exchange_assignment.subject.name}) ← " +
                       f"3年3組({parent_assignment.subject.name}) {status}")
    elif parent_assignment:
        logger.info(f"3年3組の金曜5限: {parent_assignment.subject.name}")
    else:
        logger.warning("3年3組の金曜5限: 空欄のまま")


if __name__ == "__main__":
    main()