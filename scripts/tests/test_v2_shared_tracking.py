#!/usr/bin/env python3
"""
統一ハイブリッド戦略V2の共有日内科目追跡のテストスクリプト

共有追跡の実装により日内重複違反が減少することを確認します。
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.config.logging_config import LoggingConfig
from src.application.services.data_loading_service import DataLoadingService
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.application.services.generation_strategies.unified_hybrid_strategy_v2 import UnifiedHybridStrategyV2
from src.domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraintRefactored
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository


def test_shared_tracking():
    """共有追跡のテスト"""
    print("=== 統一ハイブリッド戦略V2 共有追跡テスト ===\n")
    
    # Configure logging
    LoggingConfig.setup_logging(log_level='WARNING', simple_format=True)
    
    # Initialize services
    path_manager = PathManager()
    data_loader = DataLoadingService()
    
    # Load data
    school, use_enhanced = data_loader.load_school_data(path_manager.data_dir)
    initial_schedule = data_loader.load_initial_schedule(
        path_manager.data_dir, 
        "input.csv",
        start_empty=False,
        validate=False
    )
    
    # Create constraint system
    from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
    constraint_system = UnifiedConstraintSystem()
    constraint_service = ConstraintRegistrationService()
    constraint_service.register_all_constraints(
        constraint_system, path_manager.data_dir
    )
    
    # Generate with V2
    print("統一ハイブリッド戦略V2で生成中...")
    generator = UnifiedHybridStrategyV2(constraint_system)
    schedule = generator.generate(school, initial_schedule)
    
    # Check daily duplicate violations
    print("\n日内重複チェック中...")
    daily_duplicate_constraint = DailyDuplicateConstraintRefactored()
    result = daily_duplicate_constraint.validate(schedule, school)
    violations = result.violations
    
    print(f"\n日内重複違反数: {len(violations)}件")
    
    if violations:
        print("\n違反の詳細（最初の10件）:")
        for i, violation in enumerate(violations[:10], 1):
            print(f"{i}. {violation.description}")
    else:
        print("\n✅ 日内重複違反なし！共有追跡が正しく機能しています。")
    
    # Save the generated schedule
    output_path = path_manager.get_output_path("test_v2_shared_tracking.csv")
    csv_repo = CSVScheduleRepository(path_manager.data_dir)
    csv_repo.save(schedule, str(output_path))
    print(f"\n生成されたスケジュールを保存: {output_path}")
    
    # Compare with old violations count
    print("\n改善効果:")
    print("- 改善前: 18件の日内重複違反")
    print(f"- 改善後: {len(violations)}件の日内重複違反")
    if len(violations) < 18:
        reduction = 18 - len(violations)
        percentage = (reduction / 18) * 100
        print(f"- 削減数: {reduction}件 ({percentage:.1f}%改善)")
    
    return len(violations)


if __name__ == "__main__":
    violations_count = test_shared_tracking()
    
    # Exit with error code if violations still exist
    sys.exit(0 if violations_count == 0 else 1)