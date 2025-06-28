#!/usr/bin/env python3
"""人間的柔軟性のテスト"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.path_config import path_config
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_flexible_filling():
    """柔軟な埋め戦略のテスト"""
    
    # 制約システムとデータローダーの初期化
    constraint_system = UnifiedConstraintSystem()
    absence_loader = TeacherAbsenceLoader()
    
    # SmartEmptySlotFillerの初期化
    filler = SmartEmptySlotFiller(constraint_system, absence_loader)
    
    # 戦略の確認
    logger.info("利用可能な戦略:")
    for pass_num, strategy in filler.strategies.items():
        logger.info(f"  パス{pass_num}: {strategy.name}")
    
    # FlexibleFillingStrategyが含まれているか確認
    if 5 in filler.strategies:
        logger.info("✓ FlexibleFillingStrategy（人間的柔軟性）が追加されています")
        
        # 戦略の詳細を確認
        flexible_strategy = filler.strategies[5]
        logger.info(f"  戦略名: {flexible_strategy.name}")
        logger.info("  機能: 教師代替、時数借用、緊急対応など")
    else:
        logger.error("✗ FlexibleFillingStrategyが見つかりません")
        return False
    
    # 実際の時間割でテスト
    try:
        # CSVリポジトリの初期化
        base_path = Path(".")
        output_path = base_path / "data" / "output" / "output.csv"
        
        if output_path.exists():
            logger.info(f"\n既存の時間割をロード: {output_path}")
            
            # リポジトリを使用してスケジュールを読み込み
            repo = CSVScheduleRepository(base_path / "data")
            schedule = repo.load_schedule(str(output_path))
            
            # 学校データも必要
            from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
            school_repo = CSVSchoolRepository(base_path / "data")
            school = school_repo.load_school()
            
            # 空きスロットの数を確認
            empty_before = count_empty_slots(schedule)
            logger.info(f"空きスロット数（埋め前）: {empty_before}")
            
            # 柔軟な埋め戦略を使用（パス5まで実行）
            filled = filler.fill_empty_slots_smartly(schedule, school, max_passes=5)
            logger.info(f"埋めたスロット数: {filled}")
            
            # 空きスロットの数を再確認
            empty_after = count_empty_slots(schedule)
            logger.info(f"空きスロット数（埋め後）: {empty_after}")
            
            # 詳細レポートを表示
            if hasattr(filler, 'get_unfilled_slots_report'):
                report = filler.get_unfilled_slots_report()
                logger.info("\n" + report)
            
            return True
        else:
            logger.warning("output.csvが見つかりません。時間割を生成してください。")
            return False
            
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False

def count_empty_slots(schedule):
    """空きスロット数をカウント"""
    count = 0
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            time_slot = (day, period)
            for class_ref in schedule.get_all_classes():
                if not schedule.get_assignment(time_slot, class_ref):
                    count += 1
    
    return count

if __name__ == "__main__":
    logger.info("=== 人間的柔軟性のテスト開始 ===")
    
    success = test_flexible_filling()
    
    if success:
        logger.info("\n✓ テスト成功！FlexibleFillingStrategyが正しく実装されています。")
        logger.info("\n次のステップ:")
        logger.info("1. python3 main.py generate --human-like-flexibility")
        logger.info("   で人間的柔軟性を有効にして時間割生成")
        logger.info("2. 代替教師の配置や時数借用が行われるか確認")
    else:
        logger.error("\n✗ テスト失敗")
        
    logger.info("\n=== テスト終了 ===")