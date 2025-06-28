#!/usr/bin/env python3
"""教師検出のテストスクリプト"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import logging
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.domain.value_objects.time_slot import TimeSlot, Subject

# ログ設定
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_teacher_detection():
    """教師検出の動作テスト"""
    path_manager = PathManager()
    repo = CSVScheduleRepository()
    
    # 学校情報を読み込み
    logger.info("=== 学校情報読み込み ===")
    school = repo.get_school()
    
    # 初期スケジュールを読み込み
    logger.info("\n=== 初期スケジュール読み込み ===")
    reader = CSVScheduleReader()
    schedule = reader.read(path_manager.input_dir / "input.csv")
    
    logger.info(f"初期割り当て数: {len(schedule.get_all_assignments())}")
    
    # いくつかの配置から教師を取得してみる
    logger.info("\n=== 教師取得テスト ===")
    count = 0
    for time_slot, assignment in list(schedule.get_all_assignments())[:10]:
        logger.info(f"\n{time_slot.day}{time_slot.period}限 {assignment.class_ref}:")
        logger.info(f"  科目: {assignment.subject.name}")
        logger.info(f"  教師（assignment内）: {assignment.teacher}")
        
        # Subjectオブジェクトを作成
        subject_obj = Subject(assignment.subject.name)
        teacher = school.get_assigned_teacher(subject_obj, assignment.class_ref)
        logger.info(f"  教師（school取得）: {teacher}")
        
        if teacher:
            count += 1
    
    logger.info(f"\n教師を取得できた配置: {count}/10")
    
    # teacher_subject_mappingの内容を確認
    logger.info("\n=== teacher_subject_mapping.csvの内容 ===")
    mapping_file = path_manager.config_dir / "teacher_subject_mapping.csv"
    if mapping_file.exists():
        with open(mapping_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:10]
            for line in lines:
                logger.info(line.strip())

if __name__ == "__main__":
    test_teacher_detection()