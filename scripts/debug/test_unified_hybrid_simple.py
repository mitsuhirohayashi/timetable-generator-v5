#!/usr/bin/env python3
"""統一ハイブリッド戦略の簡単なテスト"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.application.services.data_loading_service import DataLoadingService
from src.application.services.generation_strategies.unified_hybrid_strategy import UnifiedHybridStrategy
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.config.path_config import path_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_unified_hybrid():
    """統一ハイブリッド戦略をテスト"""
    try:
        # データ読み込みサービスの初期化
        data_loading_service = DataLoadingService()
        
        # 学校データの読み込み
        logger.info("学校データを読み込み中...")
        school, use_enhanced_features = data_loading_service.load_school_data(path_config.data_dir)
        
        # 初期スケジュールの読み込み
        logger.info("初期スケジュールを読み込み中...")
        initial_schedule = data_loading_service.load_initial_schedule(
            path_config.data_dir,
            "input.csv",
            start_empty=False,
            validate=False
        )
        
        # 制約システムの初期化
        constraint_system = UnifiedConstraintSystem()
        
        # 統一ハイブリッド戦略の初期化と実行
        logger.info("統一ハイブリッド戦略を実行中...")
        strategy = UnifiedHybridStrategy(constraint_system)
        
        # スケジュール生成
        generated_schedule = strategy.generate(
            school=school,
            initial_schedule=initial_schedule,
            max_iterations=100
        )
        
        # 結果の表示
        logger.info("\n=== 生成結果 ===")
        all_assignments = generated_schedule.get_all_assignments()
        logger.info(f"総割り当て数: {len(all_assignments)}")
        
        # 制約違反のチェック
        validation_result = constraint_system.validate_schedule(generated_schedule, school)
        logger.info(f"制約違反数: {len(validation_result.violations)}")
        
        # 教師重複のチェック
        teacher_conflicts = strategy.teacher_tracker.get_conflicts()
        logger.info(f"教師重複数: {len(teacher_conflicts)}")
        
        if teacher_conflicts:
            logger.info("\n最初の5件の教師重複:")
            for i, (teacher, day, period, classes) in enumerate(teacher_conflicts[:5]):
                logger.info(f"  {i+1}. {teacher}先生: {day}{period}限 - {', '.join(classes)}")
        
        return generated_schedule
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_unified_hybrid()