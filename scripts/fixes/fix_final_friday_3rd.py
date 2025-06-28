#!/usr/bin/env python3
"""3年3組の金曜3限の空欄を修正するスクリプト"""
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
    """3年3組の金曜3限の空欄を修正"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 3年3組の金曜3限を確認
    class_ref = ClassReference(3, 3)
    time_slot = TimeSlot("金", 3)
    
    current_assignment = schedule.get_assignment(time_slot, class_ref)
    if current_assignment:
        logger.info(f"金曜3限は既に{current_assignment.subject.name}が配置されています")
    else:
        logger.info("金曜3限は空欄です - 美術を配置します")
        
        # 美術を配置
        beauty_subject = Subject("美")
        beauty_teacher = school.get_assigned_teacher(beauty_subject, class_ref)
        
        if beauty_teacher:
            # 教師が利用可能か確認
            teacher_available = True
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.teacher == beauty_teacher:
                    teacher_available = False
                    break
            
            if teacher_available:
                new_assignment = Assignment(class_ref, beauty_subject, beauty_teacher)
                if schedule.assign(time_slot, new_assignment):
                    logger.info(f"✓ 金曜3限に美術({beauty_teacher.name})を配置しました")
                else:
                    logger.error("美術の配置に失敗しました")
            else:
                logger.warning("美術教師が利用できません")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    logger.info("\n3年3組の金曜日:")
    friday_subjects = {}
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("金", period), class_ref)
        if assignment:
            logger.info(f"  {period}限: {assignment.subject.name}")
            if assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
                friday_subjects[assignment.subject.name] = friday_subjects.get(assignment.subject.name, 0) + 1
    
    # 日内重複チェック
    logger.info("\n金曜日の科目配置:")
    for subject, count in friday_subjects.items():
        if count > 1:
            logger.warning(f"  {subject}: {count}回 - 日内重複!")
        else:
            logger.info(f"  {subject}: {count}回 ✓")
    
    # 全体の問題チェック
    logger.info("\n=== 全体の問題チェック ===")
    
    # 2年2組の月曜日
    logger.info("\n2年2組の月曜日:")
    mon_subjects = {}
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("月", period), ClassReference(2, 2))
        if assignment and assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
            mon_subjects[assignment.subject.name] = mon_subjects.get(assignment.subject.name, 0) + 1
    
    for subject, count in mon_subjects.items():
        if count > 1:
            logger.warning(f"  {subject}: {count}回 - 日内重複!")
        else:
            logger.info(f"  {subject}: {count}回 ✓")
    
    # 交流学級の自立活動チェック
    logger.info("\n交流学級の自立活動チェック:")
    exchange_pairs = [
        (ClassReference(2, 7), ClassReference(2, 2), TimeSlot("月", 5)),
        (ClassReference(3, 6), ClassReference(3, 3), TimeSlot("金", 5))
    ]
    
    for exchange_class, parent_class, check_slot in exchange_pairs:
        exchange_assignment = schedule.get_assignment(check_slot, exchange_class)
        parent_assignment = schedule.get_assignment(check_slot, parent_class)
        
        if exchange_assignment and parent_assignment:
            if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                status = "✓" if parent_assignment.subject.name in ["数", "英", "算"] else "✗"
                logger.info(f"  {check_slot} {exchange_class.full_name}(自立) ← " +
                           f"{parent_class.full_name}({parent_assignment.subject.name}) {status}")


if __name__ == "__main__":
    main()