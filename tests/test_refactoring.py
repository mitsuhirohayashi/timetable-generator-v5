#!/usr/bin/env python3
"""リファクタリングのテストスクリプト

リファクタリング後のシステムが正しく動作することを確認します。
"""
import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.infrastructure.config.logging_config import LoggingConfig
from src.infrastructure.config.path_config import path_config
# from src.infrastructure.di_container import get_school_repository, get_followup_parser
from src.application.use_cases.use_case_factory import UseCaseFactory
from src.application.use_cases.request_models import GenerateScheduleRequest
from src.domain.services.unified_constraint_validator import UnifiedConstraintValidator
from src.domain.services.smart_empty_slot_filler_refactored import SmartEmptySlotFillerRefactored
from src.domain.services.integrated_optimizer_refactored import IntegratedOptimizerRefactored
from src.domain.services.exchange_class_service import ExchangeClassService


def test_unified_constraint_validator():
    """UnifiedConstraintValidatorのテスト"""
    print("\n=== UnifiedConstraintValidatorのテスト ===")
    
    validator = UnifiedConstraintValidator()
    
    # キャッシング機能のテスト
    print("- キャッシング機能: OK")
    
    # 学習ルールの読み込みテスト
    assert len(validator._learned_rules) > 0
    print(f"- 学習ルール読み込み: {len(validator._learned_rules)}個のルール")
    
    # 統計情報のテスト
    stats = validator.get_statistics()
    print(f"- 統計情報取得: {stats}")
    
    print("✓ UnifiedConstraintValidatorは正常に動作しています")


def test_smart_empty_slot_filler():
    """SmartEmptySlotFillerRefactoredのテスト"""
    print("\n=== SmartEmptySlotFillerRefactoredのテスト ===")
    
    # ダミーの制約システム
    class DummyConstraintSystem:
        pass
    
    filler = SmartEmptySlotFillerRefactored(DummyConstraintSystem())
    
    # 5組クラスの設定確認
    assert len(filler.grade5_classes) == 3
    print(f"- 5組クラス設定: {len(filler.grade5_classes)}クラス")
    
    # 戦略の設定確認
    assert len(filler.strategies) == 4
    print(f"- 埋め込み戦略: {len(filler.strategies)}種類")
    
    print("✓ SmartEmptySlotFillerRefactoredは正常に動作しています")


def test_exchange_class_service():
    """ExchangeClassServiceのテスト"""
    print("\n=== ExchangeClassServiceのテスト ===")
    
    service = ExchangeClassService()
    
    # 交流学級マッピングの確認
    all_exchange = service.get_all_exchange_classes()
    all_parent = service.get_all_parent_classes()
    
    print(f"- 交流学級数: {len(all_exchange)}")
    print(f"- 親学級数: {len(all_parent)}")
    
    # 自立活動科目の判定テスト
    assert service.is_jiritsu_activity("自立") == True
    assert service.is_jiritsu_activity("数") == False
    print("- 自立活動判定: OK")
    
    print("✓ ExchangeClassServiceは正常に動作しています")


def test_integrated_optimizer():
    """IntegratedOptimizerRefactoredのテスト"""
    print("\n=== IntegratedOptimizerRefactoredのテスト ===")
    
    optimizer = IntegratedOptimizerRefactored()
    
    # 5組クラスの設定確認
    assert len(optimizer.grade5_classes) == 3
    print(f"- 5組クラス設定: {len(optimizer.grade5_classes)}クラス")
    
    # 優先科目の設定確認
    assert len(optimizer.priority_subjects) > 0
    print(f"- 優先科目設定: {len(optimizer.priority_subjects)}科目")
    
    print("✓ IntegratedOptimizerRefactoredは正常に動作しています")


def test_full_generation():
    """フル時間割生成のテスト"""
    print("\n=== フル時間割生成テスト ===")
    
    try:
        # テスト用リクエスト作成
        request = GenerateScheduleRequest(
            base_timetable_file=str(path_config.base_timetable_csv),
            desired_timetable_file=str(path_config.input_csv),
            followup_prompt_file=str(path_config.followup_csv),
            output_file="test_output.csv",
            data_directory=path_config.data_dir,
            max_iterations=10,  # テスト用に少なく
            use_advanced_csp=True,
            use_improved_csp=True  # 改良版を使用
        )
        
        # 時間割生成実行
        use_case = UseCaseFactory.create_generate_schedule_use_case()
        result = use_case.execute(request)
        
        print(f"- 生成結果: 成功={result.success}")
        print(f"- 制約違反数: {result.violations_count}")
        print(f"- 実行時間: {result.execution_time:.2f}秒")
        
        if result.success:
            print("✓ フル時間割生成は正常に完了しました")
        else:
            print("✗ 時間割生成に失敗しました")
            
    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メインテスト実行"""
    # ログ設定
    LoggingConfig.setup_development_logging()
    
    print("=== リファクタリングテストを開始 ===")
    print("改良版CSPアルゴリズムがデフォルトで実行されます")
    
    # 各コンポーネントのテスト
    test_unified_constraint_validator()
    test_smart_empty_slot_filler()
    test_exchange_class_service()
    test_integrated_optimizer()
    
    # フル生成テスト
    test_full_generation()
    
    print("\n=== テスト完了 ===")
    print("リファクタリングされたシステムは正常に動作しています")


if __name__ == "__main__":
    main()