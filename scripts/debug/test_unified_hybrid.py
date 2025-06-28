#!/usr/bin/env python3
"""統一ハイブリッド戦略のテストスクリプト"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.application.services.generation_strategies.unified_hybrid_strategy import UnifiedHybridStrategy
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.infrastructure.config.path_config import path_config
from src.domain.entities.schedule import Schedule
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_unified_hybrid():
    """統一ハイブリッド戦略をテスト"""
    try:
        # リポジトリの初期化
        csv_repo = CSVRepository(str(path_config.data_dir))
        teacher_repo = TeacherMappingRepository(str(path_config.config_dir))
        
        # 学校データの読み込み
        logger.info("学校データを読み込み中...")
        school = csv_repo.load_school()
        teacher_mapping = teacher_repo.load_teacher_mapping()
        school.set_teacher_mapping(teacher_mapping)
        
        # 制約システムの初期化
        constraint_system = UnifiedConstraintSystem()
        
        # 初期スケジュールの読み込み
        logger.info("初期スケジュールを読み込み中...")
        initial_schedule = csv_repo.load_schedule(school, str(path_config.input_csv))
        
        # 統一ハイブリッド戦略の初期化
        logger.info("統一ハイブリッド戦略を初期化中...")
        strategy = UnifiedHybridStrategy(constraint_system)
        
        # スケジュール生成
        logger.info("スケジュール生成を開始...")
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
        
        if validation_result.violations:
            logger.info("\n最初の10件の違反:")
            for i, violation in enumerate(validation_result.violations[:10]):
                logger.info(f"  {i+1}. {violation}")
        
        # 教師重複のチェック
        teacher_conflicts = strategy.teacher_tracker.get_conflicts()
        logger.info(f"\n教師重複数: {len(teacher_conflicts)}")
        
        if teacher_conflicts:
            logger.info("\n最初の5件の教師重複:")
            for i, (teacher, day, period, classes) in enumerate(teacher_conflicts[:5]):
                logger.info(f"  {i+1}. {teacher}先生: {day}{period}限 - {', '.join(classes)}")
        
        # 結果を保存
        output_path = path_config.output_dir / "test_unified_hybrid_output.csv"
        csv_repo.save_schedule(generated_schedule, str(output_path))
        logger.info(f"\n結果を保存しました: {output_path}")
        
        return generated_schedule
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_unified_hybrid()