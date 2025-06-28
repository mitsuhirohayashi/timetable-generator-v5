#!/usr/bin/env python3
"""3年3組の金曜3限を別の科目で埋めるスクリプト"""
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
    """3年3組の金曜3限を利用可能な科目で埋める"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 3年3組の金曜3限
    class_ref = ClassReference(3, 3)
    time_slot = TimeSlot("金", 3)
    
    current_assignment = schedule.get_assignment(time_slot, class_ref)
    if not current_assignment:
        logger.info("金曜3限は空欄です - 利用可能な科目を探します")
        
        # 金曜日の既存科目を確認
        friday_subjects = []
        for period in range(1, 7):
            if period == 3:
                continue
            check_slot = TimeSlot("金", period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
                friday_subjects.append(assignment.subject.name)
        
        logger.info(f"金曜日の既存科目: {friday_subjects}")
        
        # 候補科目のリスト（優先順）
        candidate_subjects = ["音", "美", "保", "理", "社", "家", "技"]
        
        placed = False
        for subject_name in candidate_subjects:
            # 既に金曜日にある科目はスキップ
            if subject_name in friday_subjects:
                logger.info(f"{subject_name}は既に金曜日にあるためスキップ")
                continue
            
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            
            if not teacher:
                logger.info(f"{subject_name}の教師が見つかりません")
                continue
            
            # 教師が利用可能か確認（全クラスをチェック）
            teacher_available = True
            conflicting_class = None
            
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(time_slot, other_class)
                if other_assignment and other_assignment.teacher.name == teacher.name:
                    teacher_available = False
                    conflicting_class = other_class
                    break
            
            if teacher_available:
                new_assignment = Assignment(class_ref, subject, teacher)
                try:
                    if schedule.assign(time_slot, new_assignment):
                        logger.info(f"✓ 金曜3限に{subject_name}({teacher.name})を配置しました")
                        placed = True
                        break
                except Exception as e:
                    logger.error(f"{subject_name}の配置に失敗: {e}")
            else:
                logger.info(f"{subject_name}の{teacher.name}先生は{conflicting_class.full_name}で授業中")
        
        if not placed:
            logger.warning("どの科目も配置できませんでした")
    else:
        logger.info(f"金曜3限は既に{current_assignment.subject.name}が配置されています")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    logger.info("\n3年3組の完全な時間割:")
    
    for day in ["月", "火", "水", "木", "金"]:
        logger.info(f"\n{day}曜日:")
        for period in range(1, 7):
            ts = TimeSlot(day, period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment:
                logger.info(f"  {period}限: {assignment.subject.name}")
            else:
                logger.warning(f"  {period}限: 空欄!")


if __name__ == "__main__":
    main()