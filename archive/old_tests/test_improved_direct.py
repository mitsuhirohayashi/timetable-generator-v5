#!/usr/bin/env python3
"""改善版CSPジェネレーターの直接テスト"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.domain.services.input_data_corrector import InputDataCorrector
from src.infrastructure.config.constraint_loader import ConstraintLoader

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    """改善版CSPジェネレーターのテスト"""
    logger.info("=== 改善版CSPジェネレーター直接テスト ===")
    
    # リポジトリの初期化
    schedule_repository = CSVScheduleRepository(Path("data"))
    school_repository = CSVSchoolRepository(Path("data"))
    
    # 学校データを読み込む
    school = school_repository.load_school_data()
    initial_schedule = schedule_repository.load_desired_schedule("input/input.csv", school)
    
    # 制約システムの初期化
    constraint_system = UnifiedConstraintSystem()
    loader = ConstraintLoader()
    loader.load_all_constraints(constraint_system)
    
    # 入力データの補正
    corrector = InputDataCorrector()
    corrections = corrector.correct_input_schedule(initial_schedule, school)
    if corrections:
        logger.info(f"{len(corrections)}件の入力データを補正しました")
    
    # サービスの初期化
    service = ScheduleGenerationService(constraint_system)
    
    # 改善版CSPを明示的に指定して実行
    logger.info("use_improved_csp=Trueで実行します")
    schedule = service.generate_schedule(
        school=school,
        initial_schedule=initial_schedule,
        use_advanced_csp=False,  # 高度なCSPは無効化
        use_improved_csp=True,   # 改善版CSPを有効化
        use_ultrathink=False,    # Ultrathinkは無効化
        max_iterations=100
    )
    
    # 結果の確認
    assignments = schedule.get_all_assignments()
    logger.info(f"生成された授業数: {len(assignments)}")
    
    # 統計情報の表示
    if hasattr(service, 'generation_stats'):
        stats = service.generation_stats
        logger.info(f"使用アルゴリズム: {stats.get('algorithm_used', 'unknown')}")
        logger.info(f"制約違反数: {stats.get('violations_found', 0)}")

if __name__ == "__main__":
    main()