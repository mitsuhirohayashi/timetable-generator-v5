#!/usr/bin/env python3
"""テスト期間データの喪失箇所を追跡するスクリプト"""

import logging
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot
from src.infrastructure.config.path_manager import get_path_manager
from src.application.services.data_loading_service import DataLoadingService
from src.domain.services.input_data_corrector import InputDataCorrector

# ログレベルを設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def count_test_period_assignments(schedule, test_periods):
    """テスト期間の割り当て数をカウント"""
    count = 0
    subjects = []
    for day, period in test_periods:
        time_slot = TimeSlot(day, period)
        for time, assignment in schedule.get_all_assignments():
            if time == time_slot:
                count += 1
                subjects.append(f"{assignment.class_ref} - {assignment.subject.name}")
    return count, subjects

def main():
    logger.info("=== テスト期間データ追跡開始 ===\n")
    
    # テスト期間の定義
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),
        ("火", 1), ("火", 2), ("火", 3),
        ("水", 1), ("水", 2)
    ]
    
    path_manager = get_path_manager()
    data_dir = path_manager.data_dir
    
    # Step 1: 直接CSVを読み込む
    logger.info("Step 1: CSVScheduleRepositoryで直接読み込み")
    schedule_repo = CSVScheduleRepository(str(data_dir))
    schedule1 = schedule_repo.load_desired_schedule("input/input.csv")
    count1, subjects1 = count_test_period_assignments(schedule1, test_periods)
    logger.info(f"  テスト期間データ数: {count1}")
    if count1 > 0:
        logger.info(f"  最初の5件: {subjects1[:5]}")
    
    # Step 2: DataLoadingServiceで読み込み
    logger.info("\nStep 2: DataLoadingServiceで読み込み")
    data_loading_service = DataLoadingService()
    school, _ = data_loading_service.load_school_data(data_dir)
    schedule2 = data_loading_service.load_initial_schedule(
        data_dir, "input.csv", start_empty=False, validate=False
    )
    if schedule2:
        count2, subjects2 = count_test_period_assignments(schedule2, test_periods)
        logger.info(f"  テスト期間データ数: {count2}")
        if count2 > 0:
            logger.info(f"  最初の5件: {subjects2[:5]}")
    
    # Step 3: InputDataCorrectorを適用
    logger.info("\nStep 3: InputDataCorrectorを適用")
    if schedule2:
        corrector = InputDataCorrector()
        corrections = corrector.correct_input_schedule(schedule2, school)
        logger.info(f"  補正数: {corrections}")
        count3, subjects3 = count_test_period_assignments(schedule2, test_periods)
        logger.info(f"  テスト期間データ数: {count3}")
        if count3 > 0:
            logger.info(f"  最初の5件: {subjects3[:5]}")
    
    # Step 4: 固定科目保護の有効/無効を確認
    logger.info("\nStep 4: 固定科目保護の状態を確認")
    if schedule2:
        logger.info(f"  固定科目保護が有効: {schedule2._fixed_subject_protection_enabled}")
        
        # テスト期間の特定のセルをチェック
        logger.info("\n  特定のテスト期間セルの詳細:")
        for i, (day, period) in enumerate(test_periods[:3]):
            time_slot = TimeSlot(day, period)
            logger.info(f"\n  {day}曜{period}限:")
            count = 0
            for cls in school.get_all_classes():
                assignment = schedule2.get_assignment(time_slot, cls)
                if assignment:
                    is_locked = schedule2.is_locked(time_slot, cls)
                    logger.info(f"    {cls}: {assignment.subject.name} (ロック: {is_locked})")
                    count += 1
            logger.info(f"    → 合計: {count}クラス")
    
    logger.info("\n=== 追跡完了 ===")

if __name__ == "__main__":
    main()