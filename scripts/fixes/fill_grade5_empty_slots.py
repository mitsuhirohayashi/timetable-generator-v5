#!/usr/bin/env python3
"""5組の空きコマを埋めるスクリプト"""
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
    """5組の空きコマを埋める"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load("output/output.csv", school)
    
    # 5組のクラス
    grade5_classes = [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ]
    
    # 水曜4限に学活を配置
    time_slot = TimeSlot("水", 4)
    subject = Subject("学活")
    teacher = Teacher("金子み")  # 5組の担任
    
    logger.info(f"\n水曜4限に学活を配置します（教師: {teacher.name}）")
    
    filled_count = 0
    for class_ref in grade5_classes:
        # 現在の割り当てを確認
        current = schedule.get_assignment(time_slot, class_ref)
        
        if current:
            logger.info(f"{class_ref.full_name}: すでに{current.subject.name}が配置されています")
        else:
            # 学活を配置
            assignment = Assignment(class_ref, subject, teacher)
            try:
                schedule.assign(time_slot, assignment)
                filled_count += 1
                logger.info(f"✓ {class_ref.full_name}: 学活を配置しました")
            except Exception as e:
                logger.error(f"✗ {class_ref.full_name}: 配置に失敗 - {e}")
    
    if filled_count > 0:
        logger.info(f"\n{filled_count}クラスに学活を配置しました")
        
        # 結果を保存
        logger.info("\n結果を保存中...")
        schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
        logger.info("✓ output.csvを更新しました")
        
        # 5組の時数確認
        logger.info("\n=== 5組の更新後の時数確認 ===")
        for class_ref in grade5_classes:
            logger.info(f"\n{class_ref.full_name}:")
            
            # 主要科目の時数を集計
            subject_hours = {}
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    ts = TimeSlot(day, period)
                    assignment = schedule.get_assignment(ts, class_ref)
                    if assignment:
                        subject_name = assignment.subject.name
                        subject_hours[subject_name] = subject_hours.get(subject_name, 0) + 1
            
            # 時数を表示
            for subject_name in sorted(subject_hours.keys()):
                hours = subject_hours[subject_name]
                logger.info(f"  {subject_name}: {hours}時間")
            
            # 学活の確認
            if "学活" in subject_hours:
                logger.info(f"  → 学活が{subject_hours['学活']}時間配置されています")
    else:
        logger.warning("学活の配置が必要なクラスがありませんでした")


if __name__ == "__main__":
    main()